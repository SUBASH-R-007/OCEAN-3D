"""Single-writer public INCOIS synchronization, immutable generations and visible failures."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
import xarray as xr
from . import incois_catalog as source
from .science import Model, normalize, file_hash, SCIENCE_LOCK


def utcnow(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')


def atomic_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_suffix(path.suffix+'.pending')
    pending.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
    pending.replace(path)


def public_profiles(packet):
    """Explicit raw-channel thermodynamic conversion; adjusted channels stay in the source packet."""
    import math
    import gsw
    from .observations import validate_profile
    out=[]
    for p in packet['profiles']:
        rows=[]
        for level in p['levels']:
            r=level['raw'];z=r['depth'];t=r['temp'];s=r['psal'];pres=r['pres']
            if s is not None and s<0:s=None
            if z is None or z<0: continue
            flags=[p['time_qc'],r['qc']['pres'],r['qc']['temp'],r['qc']['psal']]
            qc=0 if 0 in flags else max(flags)
            potential=None
            if t is not None and s is not None and s>=0 and pres is not None:
                sa=gsw.SA_from_SP(s,pres,p['longitude'],p['latitude'])
                value=float(gsw.pt0_from_t(sa,t,pres))
                if math.isfinite(value): potential=value
            for variable,value,quality in [('temperature',potential,qc),('salinity',s,0 if 0 in [p['time_qc'],r['qc']['pres'],r['qc']['psal']] else max(p['time_qc'],r['qc']['pres'],r['qc']['psal']))]:
                rows.append(dict(variable=variable,value=value,depth=z,qc=quality,error=None,adjusted=False,
                                 source_temperature=t,source_pressure=pres,time=p['time']))
        if not rows: continue
        identity='sync-argo-'+hashlib.sha256(p['id'].encode()).hexdigest()[:24]
        item=dict(id=identity,instrument='Argo',longitude=p['longitude'],latitude=p['latitude'],
                  time=p['time'],samples=rows,synthetic=False,source='INCOIS public Argo table · raw channel',
                  data_mode='Unspecified by source table',source_url=packet['source_url'],sha256=packet['source_sha256'],
                  source_profile_id=p['id'],
                  source_metadata=p['source_metadata'],retrieved_at=packet['retrieved_at'],
                  warning='Raw channel selected explicitly; GSW converts in-situ temperature using raw salinity/pressure. Position QC and DATA_MODE are not provided. Adjusted channels remain in the source packet. No independent forecast skill or propagated uncertainty is claimed.')
        validate_profile(item);out.append(item)
        if len(out)>1000 or sum(len(x['samples']) for x in out)>200_000: raise ValueError('Synchronized observation budget exceeded; narrow the acquisition window.')
    return out


class Synchronizer:
    def __init__(self, folder, publish, *, enabled=False, readonly=False, interval=21600):
        if not 3600<=interval<=604800: raise ValueError('Sync interval must be 3600–604800 seconds.')
        if enabled and readonly: raise ValueError('Automatic synchronization needs the single writable service.')
        self.folder=Path(folder);self.publish=publish;self.enabled=enabled;self.readonly=readonly;self.interval=interval
        self.guard=threading.RLock();self.stop_event=threading.Event();self.wake=threading.Event();self.thread=None
        self.last_trigger=0.;self.previous=None
        self.state=dict(status='idle',last_attempt=None,last_success=None,next_check=None,error=None,products=[])
        if (self.folder/'status.json').exists():
            self.state.update(json.loads((self.folder/'status.json').read_text(encoding='utf-8')))
            if self.state['status']=='running': self.state.update(status='interrupted',error='Previous synchronization stopped before publication. Last complete data remains available.')
        if not self.enabled:self.state['next_check']=None

    def status(self):
        with self.guard:
            value=deepcopy(self.state)
        value.update(enabled=self.enabled,readonly=self.readonly,interval_seconds=self.interval,
                     can_run=not self.readonly,source='Public INCOIS ERDDAP',
                     scope='Checks publication updates; source dates determine data age. This is not a real-time operational forecast feed.')
        return value

    def save(self, **values):
        with self.guard:
            self.state.update(values)
            atomic_json(self.folder/'status.json',self.state)

    def restore(self):
        pointer=self.folder/'current.json'
        if not pointer.exists(): return
        revision=json.loads(pointer.read_text(encoding='utf-8'))['revision']
        if not re.fullmatch('[a-f0-9]{32}',revision): raise ValueError('Invalid synchronization revision.')
        directory=self.folder/'revisions'/revision
        self.activate(directory)

    def activate(self,directory,*,persist=False):
        manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
        models=[];pointer=self.folder/'current.json'
        previous_pointer=json.loads(pointer.read_text(encoding='utf-8')) if persist and pointer.exists() else None
        pointer_written=False
        try:
            for name,digest in manifest['files'].items():
                path=directory/name
                if path.resolve().parent!=directory.resolve() or file_hash(path)!=digest: raise ValueError('Synchronized source checksum mismatch.')
            catalog=json.loads((directory/'catalog.json').read_text(encoding='utf-8'))
            profiles=json.loads((directory/'profiles.json').read_text(encoding='utf-8'))
            with SCIENCE_LOCK:
                for m in manifest['models']:
                    with xr.open_dataset(directory/m['file']) as ds:
                        provenance={**m['provenance'], 'title':m['provenance']['title']+' · checked '+manifest['created_at'][:16]+'Z'}
                        models.append(Model(m['id'],normalize(ds).load(),provenance))
                if persist:
                    self.check_stop()
                    # Persist before changing the serving generation. Failed writes leave it untouched.
                    atomic_json(pointer,dict(revision=manifest['revision']));pointer_written=True
                self.publish(models,profiles)
                source.install_catalog(manifest['revision'],catalog,directory)
            self.previous=directory
        except Exception:
            for model in models: model.close()
            if pointer_written:
                if previous_pointer is None:pointer.unlink(missing_ok=True)
                else:atomic_json(pointer,previous_pointer)
            raise

    def start(self):
        if self.readonly: return
        self.thread=threading.Thread(target=self.loop,name='ocean-incois-sync',daemon=True);self.thread.start()

    def seconds_until_check(self):
        if not self.enabled:return None
        next_check=self.state.get('next_check')
        if not next_check:return 0
        try:
            due=datetime.fromisoformat(next_check.replace('Z','+00:00'))
            return min(self.interval,max(0,(due-datetime.now(timezone.utc)).total_seconds()))
        except (ValueError,TypeError):return 0

    def close(self):
        self.stop_event.set();self.wake.set()
        if self.thread:self.thread.join(timeout=55)

    def trigger(self):
        if self.readonly: raise ValueError('Synchronization is unavailable on read-only replicas.')
        with self.guard:
            if self.state['status']=='running' or self.wake.is_set() or time.monotonic()-self.last_trigger<60:
                return False
            self.last_trigger=time.monotonic();self.wake.set();return True

    def loop(self):
        while not self.stop_event.is_set():
            due=self.wake.wait(self.seconds_until_check())
            self.wake.clear()
            if self.stop_event.is_set():break
            if due or self.enabled:
                try:self.run()
                except Exception as exc:
                    logging.exception('Synchronization could not persist its status')
                    # Disk failures must not kill the scheduler or lock out manual checks.
                    with self.guard:
                        self.state.update(status='error',error='Synchronization status could not be persisted: '+str(exc)[:400],current_product=None,
                                          next_check=(datetime.now(timezone.utc)+timedelta(seconds=self.interval)).isoformat() if self.enabled else None)

    def check_stop(self):
        if self.stop_event.is_set():raise ValueError('Synchronization stopped before publication.')

    def run(self):
        if self.readonly: raise ValueError('Synchronization is unavailable on read-only replicas.')
        revision=uuid.uuid4().hex;directory=self.folder/'revisions'/revision
        self.save(status='running',last_attempt=utcnow(),error=None,next_check=None)
        published=False
        try:
            # Three retained generations plus bounded caches; stop before unbounded disk growth.
            if sum(p.stat().st_size for p in self.folder.rglob('*') if p.is_file())>1024**3:
                raise ValueError('Synchronization storage exceeds 1 GiB. Review retained files before resuming.')
            source.acquire(source.BASE+'/info/index.json?itemsPerPage=1000&page=1',directory/'catalog-source.json',2*1024*1024)
            table=json.loads((directory/'catalog-source.json').read_text(encoding='utf-8'))['table']
            identities=[dict(zip(table['columnNames'],r))['Dataset ID'] for r in table['rows']]
            identities=[i for i in identities if i!='allDatasets']
            if not 1<=len(identities)<=64 or len(set(identities))!=len(identities): raise ValueError('Unexpected source catalogue size or duplicate products.')
            for identity in identities:
                self.check_stop()
                if not re.fullmatch('[A-Za-z0-9_]+',identity):raise ValueError('Invalid source dataset ID.')
                source.acquire(f'{source.BASE}/info/{identity}/index.json',directory/(identity+'.json'),2*1024*1024)
            catalog=source.build_catalog(folder=directory,check_stop=self.check_stop)
            catalog['revision']=revision
            for p in catalog['products']:p['catalog_revision']=revision
            # Make axes available to this generation's requests without publishing it.
            source.CATALOG_REVISIONS[revision]=(catalog,directory)
            previous_catalog=json.loads((self.previous/'catalog.json').read_text(encoding='utf-8')) if self.previous else {'products':[]}
            old_products={p['id']:p for p in previous_catalog['products']}
            previous_manifest=json.loads((self.previous/'manifest.json').read_text(encoding='utf-8')) if self.previous else {'models':[]}
            models=[];profiles=[];states=[]
            for p in catalog['products']:
                self.check_stop();record=dict(id=p['id'],title=p['title'],source_end=p['end'],checked_at=utcnow())
                self.save(current_product=p['title'])
                try:
                    packet_file=p['id']+'-packet.json'
                    if p['kind']=='observations':
                        if p['id']!='Indian_ARGO_Floats':
                            record.update(status='metadata-only',detail='No reviewed native observation adapter for this product.');states.append(record);continue
                        from .incois_observations import observation_packet
                        end=datetime.fromisoformat(p['end'].replace('Z','+00:00'))
                        start=max(datetime.fromisoformat(p['start'].replace('Z','+00:00')),end-timedelta(days=1))
                        packet=observation_packet(start.isoformat(),end.isoformat(),revision=revision)
                        profiles=public_profiles(packet)
                    else:
                        packet=source.grid_packet(p,[v['id'] for v in p['variables']],len(p['times'])-1)
                        self.check_stop()
                        if p['kind']=='volume':
                            model,original=source.acquire_volume(p,len(p['times'])-1,min(3,len(p['times'])))
                            try:
                                filename=p['id']+'-model.nc'
                                with SCIENCE_LOCK:model.ds.to_netcdf(directory/filename)
                                shutil.copyfile(original,directory/(p['id']+'-source.nc'))
                                models.append(dict(id=model.id,file=filename,provenance=model.provenance))
                                p['model_id']=model.id
                            finally:model.close()
                    atomic_json(directory/packet_file,packet)
                    p['snapshot']=dict(path=f'/api/sync/snapshot/{revision}/{p["id"]}',time=packet.get('time',p['end']))
                    record.update(status='refreshed',data_time=packet.get('time',p['end']),retrieved_at=packet['retrieved_at'],source_sha256=packet['source_sha256'])
                except Exception as exc:
                    record.update(status='error',detail=str(exc)[:500])
                    old=old_products.get(p['id'])
                    if old and old.get('snapshot'):
                        for file in self.previous.glob(p['id']+'-*'):
                            if file.is_file() and not file.name.endswith('-axes.nc'):shutil.copyfile(file,directory/file.name)
                        p['snapshot']={**old['snapshot'],'path':f'/api/sync/snapshot/{revision}/{p["id"]}'}
                        if old.get('model_id'):
                            p['model_id']=old['model_id'];models.extend(m for m in previous_manifest['models'] if m['id']==old['model_id'])
                        if p['id']=='Indian_ARGO_Floats':profiles=json.loads((self.previous/'profiles.json').read_text(encoding='utf-8'))
                        record['retained_data_time']=old['snapshot']['time']
                    p['sync_error']=record['detail']
                states.append(record);self.save(products=states)
            self.check_stop()
            atomic_json(directory/'catalog.json',catalog);atomic_json(directory/'profiles.json',profiles)
            manifest=dict(revision=revision,created_at=utcnow(),models=models,
                          files={p.name:file_hash(p) for p in directory.iterdir() if p.is_file()})
            atomic_json(directory/'manifest.json',manifest)
            self.activate(directory,persist=True);published=True
            failures=sum(p['status']=='error' for p in states)
            self.save(status='partial' if failures else 'ok',last_success=utcnow(),revision=revision,
                      products=states,error=f'{failures} products could not refresh; retained data is labelled.' if failures else None)
            self.prune()
        except Exception as exc:
            self.save(status='error',error=str(exc)[:500])
        finally:
            if not published:
                # Preserve recovery data even if rolling back the pointer itself failed.
                pointer=self.folder/'current.json'
                referenced=pointer.exists() and json.loads(pointer.read_text(encoding='utf-8')).get('revision')==revision
                if not referenced:
                    source.CATALOG_REVISIONS.pop(revision,None)
                    if directory.exists() and directory.resolve().parent==(self.folder/'revisions').resolve():shutil.rmtree(directory)
            self.save(current_product=None,next_check=(datetime.now(timezone.utc)+timedelta(seconds=self.interval)).isoformat() if self.enabled else None)

    def prune(self):
        revisions=sorted((self.folder/'revisions').iterdir(),key=lambda p:p.stat().st_mtime,reverse=True)
        for directory in revisions[3:]:
            if directory.is_dir() and re.fullmatch('[a-f0-9]{32}',directory.name) and directory.resolve().parent==(self.folder/'revisions').resolve() and directory!=self.previous:
                source.CATALOG_REVISIONS.pop(directory.name,None)
                shutil.rmtree(directory)

    def snapshot_path(self,revision,product):
        if not re.fullmatch('[a-f0-9]{32}',revision) or not re.fullmatch('[A-Za-z0-9_]+',product):raise ValueError('Invalid snapshot identity.')
        directory=self.folder/'revisions'/revision
        if revision not in source.CATALOG_REVISIONS:raise ValueError('Snapshot revision expired; refresh the source library.')
        path=directory/(product+'-packet.json')
        if not path.exists():raise ValueError('No synchronized data packet for this product; inspect its refresh status.')
        return path
