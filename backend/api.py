from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
import json
import os
import secrets
import threading
import uuid
import logging
import hashlib
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field
from typing import Literal
from .science import Model, open_bounded_model, file_hash, SCIENCE_LOCK
from .observations import ADAPTERS
from .analysis import compare, coverage, transect
from .demo import build_demo
from .diagnostics import diagnose_model, diagnose_observation
from .reference import load_reference
from .hycom import load_currents
from .incois import load_incois
from .exports import coverage_json, subset_netcdf
from .plugins import (load_variable_plugins, load_adapter_plugins, unregister_adapters, ADAPTER_METADATA,
                      MODEL_ADAPTERS, SENSORS, PRODUCTS, EXTENSIONS, registry_snapshot, restore_registries, load_extension_plugins)
from .ingestion import adapter_specs, detect_adapter, prepare_import
from .archive import load_archives
from .transport import ByteCache, encode_volume, MEDIA_TYPE
from .server import ServerSettings
from starlette.concurrency import run_in_threadpool
from fastapi.responses import Response, JSONResponse

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.environ.get('OCEAN_DATA_DIR',str(ROOT/'data'/'imports')))
MODELS={};PROFILES={};LOCK=SCIENCE_LOCK
FRAME_CACHE=ByteCache()
SETTINGS=ServerSettings.from_env()
MAX_ACTIVE=SETTINGS.max_active
WORK_SLOTS=threading.BoundedSemaphore(MAX_ACTIVE)
WORK_STATE={'active':0,'rejected':0}
WORK_LOCK=threading.Lock()
SYNC=None
SYNC_MODEL_HISTORY=[]


def publish_synchronized(models,profiles):
    """Swap a complete source generation while scientific reads hold the same lock."""
    with LOCK:
        identities={m.id for m in models}
        planned=SYNC_MODEL_HISTORY[-2:]+[identities]
        if len(set().union(*planned))+sum(not k.startswith('sync-') for k in MODELS)>32:
            raise ValueError('The model catalogue is full; synchronization retained the previous generation.')
        SYNC_MODEL_HISTORY.append(identities)
        del SYNC_MODEL_HISTORY[:-3]
        keep=set().union(*SYNC_MODEL_HISTORY)
        for identity in list(MODELS):
            if identity.startswith('sync-') and identity not in keep:MODELS.pop(identity).close()
        for model in models:
            if model.id in MODELS:model.close()
            else:MODELS[model.id]=model
        for identity in list(PROFILES):
            if identity.startswith('sync-argo-'):PROFILES.pop(identity)
        PROFILES.update({p['id']:p for p in profiles})
        FRAME_CACHE.clear()

def register(path, kind, identity, title=None, expected_sha256=None, expected_contract=None):
    if identity in MODELS or any(pid.startswith(identity+':') for pid in PROFILES):
        raise ValueError('Dataset identity is already registered.')
    if expected_sha256 and file_hash(path) != expected_sha256:
        raise ValueError('Stored import checksum does not match its manifest; restore the original source file.')
    if expected_contract and ADAPTER_METADATA.get(kind,{}).get('plugin')!=expected_contract:
        raise ValueError('Stored adapter version differs from the installed extension; restore its pinned version or migrate the import.')
    model,parsed,report=prepare_import(path,kind,identity,title or path.name)
    if model:
        MODELS[identity]=model
    else:
        pending_profiles={}
        for p in parsed:
            p['id']=identity+':'+p['id']
            if p.get('trajectory_id'): p['trajectory_id']=identity+':'+p['trajectory_id']
            p['sha256']=report['sha256']
            if p['id'] in pending_profiles: raise ValueError('Duplicate profile IDs in one import.')
            pending_profiles[p['id']]=p
        PROFILES.update(pending_profiles)
    return report

@asynccontextmanager
async def dataset_lifespan(app):
    global SYNC
    app.state.ready=False
    app.state.restore_errors=0
    app.state.catalog_revision=None
    added_variables = []
    added_adapters = []
    if os.environ.get('OCEAN_VARIABLE_MANIFEST'):
        added_variables = load_variable_plugins(os.environ['OCEAN_VARIABLE_MANIFEST'])
    if os.environ.get('OCEAN_ADAPTER_MODULES'):
        try: added_adapters=load_adapter_plugins(os.environ['OCEAN_ADAPTER_MODULES'])
        except Exception:
            from .science import VARIABLES
            for key in added_variables: VARIABLES.pop(key,None)
            raise
    modules='backend.extensions.sensors,backend.extensions.products'
    additional=os.environ.get('OCEAN_EXTENSION_MODULES','backend.extensions.example_product')
    if additional: modules+=','+additional
    load_extension_plugins(modules)
    model,profiles=build_demo();MODELS[model.id]=model;PROFILES.update({p['id']:p for p in profiles})
    reference=load_reference()
    if reference:
        model,profiles=reference;MODELS[model.id]=model;PROFILES.update({p['id']:p for p in profiles})
    incois=load_incois()
    if incois:
        model,_=incois;MODELS[model.id]=model
    from .incois_catalog import load_basin_models
    for model in load_basin_models(): MODELS[model.id]=model
    currents=load_currents()
    if currents: MODELS[currents.id]=currents
    from .instrument_sources import load_instrument_cases
    for profile in load_instrument_cases(): PROFILES[profile['id']]=profile
    if os.environ.get('OCEAN_ARCHIVE_MANIFEST'):
        try:
            for model in load_archives(os.environ['OCEAN_ARCHIVE_MANIFEST'], MODELS): MODELS[model.id]=model
        except Exception:
            for model in MODELS.values(): model.close()
            MODELS.clear();PROFILES.clear()
            from .science import VARIABLES
            for key in added_variables: VARIABLES.pop(key, None)
            unregister_adapters(added_adapters)
            raise
    if not SETTINGS.readonly: DATA.mkdir(parents=True,exist_ok=True)
    for manifest in DATA.glob('*.json'):
        try:
            info=json.loads(manifest.read_text(encoding='utf-8')); register(DATA/info['file'],info['kind'],info['id'],info['title'],info.get('sha256'),info.get('adapter_contract'))
        except Exception:
            app.state.restore_errors+=1
            logging.exception('Failed restoring dataset manifest %s',manifest.name)
    from .synchronization import Synchronizer
    sync_setting=os.environ.get('OCEAN_SYNC_ENABLED','false').lower()
    if sync_setting not in ('true','false'):raise ValueError('OCEAN_SYNC_ENABLED must be true or false.')
    SYNC=Synchronizer(DATA/'.sync',publish_synchronized,enabled=sync_setting=='true',readonly=SETTINGS.readonly,
                      interval=int(os.environ.get('OCEAN_SYNC_INTERVAL','21600')))
    try:SYNC.restore()
    except Exception:
        app.state.restore_errors+=1
        logging.exception('Failed restoring synchronized sources')
    revision={'models':[MODELS[key].catalog() for key in sorted(MODELS)],
              'profiles':[{key:p.get(key) for key in ('id','sha256','time','variables')} for _,p in sorted(PROFILES.items())]}
    app.state.catalog_revision=hashlib.sha256(json.dumps(revision,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    app.state.ready=bool(MODELS) and app.state.restore_errors==0
    SYNC.start()
    try:
        yield
    finally:
        await run_in_threadpool(SYNC.close)
        app.state.ready=False
        for model in MODELS.values(): model.close()
        MODELS.clear();PROFILES.clear();FRAME_CACHE.clear()
        from .science import VARIABLES
        for key in added_variables: VARIABLES.pop(key, None)
        unregister_adapters(added_adapters)

@asynccontextmanager
async def lifespan(app):
    snapshot=registry_snapshot()
    try:
        async with dataset_lifespan(app): yield
    finally:
        from .incois_catalog import reset_catalog
        if SYNC:await run_in_threadpool(SYNC.close)
        SYNC_MODEL_HISTORY.clear();reset_catalog()
        for model in MODELS.values(): model.close()
        MODELS.clear();PROFILES.clear();FRAME_CACHE.clear()
        restore_registries(snapshot)


app=FastAPI(title='Ocean3D scientific API',version='1.2.0',lifespan=lifespan,
            docs_url='/api/docs',redoc_url=None,openapi_url='/api/openapi.json')
from .ogc import router as ogc_router
app.include_router(ogc_router)
from .incois_routes import router as incois_router
app.include_router(incois_router)
from .sync_routes import router as sync_router
app.include_router(sync_router)
app.add_middleware(GZipMiddleware,minimum_size=1000)
app.add_middleware(CORSMiddleware,allow_origins=os.environ.get('OCEAN_ORIGINS','http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173').split(','),allow_methods=['GET','POST'],allow_headers=['Content-Type','Authorization','Idempotency-Key'])

@app.middleware('http')
async def access(request:Request,call_next):
    token=os.environ.get('OCEAN_API_TOKEN')
    if token and request.url.path.startswith('/api/') and request.url.path not in ('/api/health','/api/ready'):
        if not secrets.compare_digest(request.headers.get('Authorization',''),f'Bearer {token}'):
            return JSONResponse({'detail':'API token required.'},status_code=401)
    if SETTINGS.readonly and (request.url.path.startswith('/api/import') or request.url.path=='/api/sync/run' or
            (request.url.path.startswith('/api/incois/') and request.url.path!='/api/incois/catalog')):
        return JSONResponse({'detail':'This read-only archive service does not accept uploads or upstream data acquisition. Publish an updated archive through the single ingestion service.'},status_code=403)
    bounded = request.url.path.startswith(('/api/volume','/api/profiles/','/api/coverage','/api/diagnostics','/api/export/','/api/transect','/api/ogc/','/api/import','/api/incois/grid','/api/incois/open','/api/incois/observations'))
    if not bounded: return await call_next(request)
    if not WORK_SLOTS.acquire(blocking=False):
        with WORK_LOCK: WORK_STATE['rejected']+=1
        return JSONResponse({'detail':'Scientific service is at capacity. Retry shortly.'},status_code=503,headers={'Retry-After':'2'})
    with WORK_LOCK: WORK_STATE['active']+=1
    try:
        return await call_next(request)
    finally:
        with WORK_LOCK: WORK_STATE['active']-=1
        WORK_SLOTS.release()

@app.exception_handler(ValueError)
async def invalid(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({'detail':str(exc)},status_code=422)

def model_for(identity):
    if identity not in MODELS: raise HTTPException(404,'Model not found.')
    return MODELS[identity]

@app.get('/api/health')
async def health(): return {'status':'ok','version':app.version,'mode':'scientific-api'}

@app.get('/api/ready')
async def ready():
    available=getattr(app.state,'ready',False)
    return JSONResponse({'status':'ready' if available else 'not-ready','mode':SETTINGS.mode,
        'capabilities':{'imports':not SETTINGS.readonly,'upstream_acquisition':not SETTINGS.readonly},
        'models':len(MODELS),'profiles':len(PROFILES),
        'restore_errors':getattr(app.state,'restore_errors',0)},status_code=200 if available else 503,
        headers={'Cache-Control':'no-store',**({} if available else {'Retry-After':'2'})})

@app.get('/api/runtime')
def runtime():
    with WORK_LOCK: work=dict(WORK_STATE,limit=MAX_ACTIVE)
    return {'scope':'this API process','frames':FRAME_CACHE.stats(),'work':work,
            'deployment':{'mode':SETTINGS.mode,'worker_pid':os.getpid(),'configured_workers':SETTINGS.workers,
                          'startup_catalog_revision':getattr(app.state,'catalog_revision',None),
                          'ready':getattr(app.state,'ready',False)},
            'policy':'Bounded in-flight requests; serialized scientific reads; 64 MiB cached payload budget. Health remains available under load.'}

@app.get('/api/catalog')
def catalog():
    from .science import VARIABLES
    with LOCK:
        return {'models':[m.catalog() for m in MODELS.values()],'profiles':[{**{k:v for k,v in p.items() if k!='samples'},'variables':sorted({row['variable'] for row in p['samples']})} for p in PROFILES.values()],'variables':[{'id':key,**meta} for key,meta in VARIABLES.items()],'mode':'scientific-api'}

@app.get('/api/adapters')
def adapters():
    from .science import VARIABLES
    return {'observations': list(ADAPTERS), 'model': 'model', 'formats':adapter_specs(), 'variables': [{'id': k, **v} for k,v in VARIABLES.items()], 'limits':{'upload_bytes':50*1024*1024,'observation_profiles':10000,'delimited_values':200000}, 'plugin_policy': 'Administrator-owned code and canonical-unit JSON definitions; data imports cannot execute plugins.'}


@app.get('/api/extensions')
def extensions():
    from .science import VARIABLES
    return {'api_version':1,'plugins':list(EXTENSIONS.values()),'sensors':list(SENSORS.values()),
            'products':list(PRODUCTS.values()),'variables':[{'id':key,**meta} for key,meta in VARIABLES.items() if meta.get('plugin')],
            'formats':adapter_specs(),'policy':'Installed administrator code only. Uploaded files never install plugins or execute model artifacts.'}

def volume_response(model,variable,index,resolution,maximum_depth,bbox,binary):
    bounds=tuple(float(v) for v in bbox.split(',')) if bbox is not None else None
    key=(model,variable,index,resolution,maximum_depth,bounds,binary)
    cached=FRAME_CACHE.get(key)
    if cached is None:
        with LOCK:
            cached=FRAME_CACHE.get(key)
            if cached is None:
                field=model_for(model).volume(variable,index,resolution,maximum_depth,bounds)
                cached=encode_volume(field) if binary else json.dumps(field,separators=(',',':'),allow_nan=False).encode()
                FRAME_CACHE.put(key,cached)
    return Response(cached,media_type=MEDIA_TYPE if binary else 'application/json',
                    headers={'Cache-Control':'private, max-age=0, must-revalidate','X-Ocean-Frame-Bytes':str(len(cached)),
                             'X-Ocean-Worker':str(os.getpid())})

@app.get('/api/volume')
def volume(model:str='demo-bob',variable:str='temperature',index:int=Query(2,ge=0),resolution:int=Query(36,ge=8,le=64),maximum_depth:float|None=Query(None,gt=0,le=12000),bbox:str|None=None):
    return volume_response(model,variable,index,resolution,maximum_depth,bbox,False)

@app.get('/api/volume.bin')
def volume_binary(model:str='demo-bob',variable:str='temperature',index:int=Query(2,ge=0),resolution:int=Query(36,ge=8,le=64),maximum_depth:float|None=Query(None,gt=0,le=12000),bbox:str|None=None):
    return volume_response(model,variable,index,resolution,maximum_depth,bbox,True)

@app.get('/api/profiles/{identity:path}')
def profile(identity:str,model:str='demo-bob',variable:str='temperature',qc:Literal['strict','lenient']='strict',max_gap_hours:float=Query(48,gt=0,le=168)):
    if identity not in PROFILES: raise HTTPException(404,'Profile not found.')
    with LOCK: return compare(model_for(model),PROFILES[identity],variable,qc,max_gap_hours)

@app.get('/api/coverage')
def coverage_route(model:str='demo-bob',variable:str='temperature',index:int=Query(2,ge=0),qc:Literal['strict','lenient']='strict'):
    with LOCK:
        m=model_for(model)
        if index>=m.ds.sizes['time']: raise ValueError('Time index unavailable.')
        return coverage(m,list(PROFILES.values()),variable,index,qc)


@app.get('/api/diagnostics')
def diagnostics(model:str='demo-bob',longitude:float=Query(85.2,ge=-180,le=180),latitude:float=Query(14.8,ge=-89,le=89),index:int=Query(2,ge=0),reference:float=Query(10,ge=0,le=100),density_delta:float=Query(.03,ge=.01,le=.2),profile:str|None=None):
    with LOCK:
        result=diagnose_model(model_for(model),longitude,latitude,index,reference,density_delta)
        if profile:
            if profile not in PROFILES: raise HTTPException(404,'Profile not found.')
            try: result['observation']=diagnose_observation(PROFILES[profile],reference,density_delta)
            except ValueError as exc: result['observation_unavailable']=str(exc)
        return result


@app.get('/api/export/column.covjson')
def export_column(model:str='demo-bob',variable:str='temperature',index:int=Query(2,ge=0),longitude:float=Query(85.2,ge=-180,le=180),latitude:float=Query(14.8,ge=-90,le=90)):
    with LOCK:
        return JSONResponse(coverage_json(model_for(model),variable,longitude,latitude,index),media_type='application/prs.coverage+json',headers={'Content-Disposition':'attachment; filename="ocean3d-column.covjson"'})


@app.get('/api/export/subset.nc')
def export_subset(model:str='demo-bob',variable:str='temperature',index:int=Query(2,ge=0),bbox:str|None=None,maximum_depth:float|None=Query(None,gt=0,le=12000)):
    bounds=[float(v) for v in bbox.split(',')] if bbox else None
    with LOCK:
        return Response(subset_netcdf(model_for(model),variable,index,bounds,maximum_depth),media_type='application/x-netcdf',headers={'Content-Disposition':'attachment; filename="ocean3d-subset.nc"'})

class TransectQuery(BaseModel):
    model:str='demo-bob'
    variable:str='temperature'
    index:int=Field(2,ge=0)
    start:tuple[float,float]
    end:tuple[float,float]

@app.post('/api/transect')
def section(q:TransectQuery):
    import numpy as np
    if not np.isfinite([*q.start,*q.end]).all(): raise ValueError('Transect coordinates must be finite.')
    with LOCK:
        m=model_for(q.model)
        if q.index>=m.ds.sizes['time']: raise ValueError('Time index unavailable.')
        return transect(m,q.variable,q.index,q.start,q.end)

@app.post('/api/import',status_code=201)
async def ingest(request:Request,kind:str='auto',file:UploadFile=File(...)):
    return await receive_import(request,kind,file)

@app.post('/api/import/inspect')
async def inspect_import(request:Request,kind:str='auto',file:UploadFile=File(...)):
    return await receive_import(request,kind,file,preview=True)

async def receive_import(request,kind,file,preview=False):
    if kind not in ('auto','model') and kind not in ADAPTERS and kind not in MODEL_ADAPTERS:
        await file.close()
        raise HTTPException(422,'Unknown import adapter.')
    identity=uuid.uuid4().hex
    path=DATA/(identity+'.upload'); size=0
    try:
        with path.open('wb') as stream:
            while block:=await file.read(1024*1024):
                size+=len(block)
                if size>50*1024*1024: raise HTTPException(413,'Import limit is 50 MiB. Subset large files upstream or mount preprocessed data.')
                stream.write(block)
        if not size: raise ValueError('The uploaded file is empty.')
        title=(file.filename or 'Imported dataset').replace('\\','/').rsplit('/',1)[-1][:200]
        def finish_import():
            nonlocal path
            digest=file_hash(path)
            with LOCK:
                resolved=detect_adapter(path,kind)
                if preview:
                    model,_,report=prepare_import(path,resolved,identity,title)
                    if model: model.close()
                    path.unlink(missing_ok=True)
                    return report
                suffix='.nc' if ADAPTER_METADATA.get(resolved,{}).get('container')=='netcdf' else '.txt'
                destination=DATA/(identity+suffix)
                path.replace(destination);path=destination
                key=request.headers.get('Idempotency-Key')
                if key:
                    if key != digest+':'+kind: raise ValueError('Idempotency-Key must equal SHA256:adapter for this payload.')
                    for existing in DATA.glob('*.json'):
                        try: info=json.loads(existing.read_text(encoding='utf-8'))
                        except (ValueError,OSError): continue
                        if info.get('sha256') == digest and info.get('kind') == resolved and info.get('adapter_contract')==ADAPTER_METADATA.get(resolved,{}).get('plugin') and (info['id'] in MODELS or any(p.startswith(info['id']+':') for p in PROFILES)):
                            path.unlink(missing_ok=True)
                            return {'id':info['id'],'kind':resolved,'bytes':size,'sha256':digest,'duplicate':True,'report':info.get('report')}
                report=register(path,resolved,identity,title)
                pending=DATA/(identity+'.pending')
                pending.write_text(json.dumps(dict(id=identity,file=path.name,kind=resolved,title=title,sha256=digest,report=report,adapter_contract=report.get('adapter_contract'))),encoding='utf-8')
                pending.replace(DATA/(identity+'.json'))
                FRAME_CACHE.clear()
            return {'id':identity,'kind':resolved,'bytes':size,'sha256':digest,'report':report}
        return await run_in_threadpool(finish_import)
    except Exception as exc:
        def rollback_import():
            with LOCK:
                if identity in MODELS: MODELS.pop(identity).close()
                for pid in list(PROFILES):
                    if pid.startswith(identity+':'): PROFILES.pop(pid)
                path.unlink(missing_ok=True)
                (DATA/(identity+'.pending')).unlink(missing_ok=True)
        await run_in_threadpool(rollback_import)
        if isinstance(exc,(HTTPException,ValueError)): raise
        logging.exception('Import failed')
        raise HTTPException(422,'Unable to parse this file. Check its format, CF metadata and coordinate dimensions.') from exc
    finally: await file.close()
