"""One validation contract for preview, direct upload, plugins and inbox producers."""
from collections import Counter
import numpy as np
import xarray as xr
from .observations import ADAPTERS, validate_profile
from .plugins import ADAPTER_METADATA, ADAPTER_DETECTORS, MODEL_ADAPTERS, SENSORS
from .science import VARIABLES, Model, open_bounded_model, bound_model, file_hash


def adapter_specs():
    return [{'id':kind,**ADAPTER_METADATA.get(kind,{'label':kind,'container':'text'}),
             'category':'model' if kind=='model' or kind in MODEL_ADAPTERS else 'observations',
             'accept':'.nc,.nc4,.cdf' if ADAPTER_METADATA.get(kind,{}).get('container')=='netcdf' else '.csv,.tsv,.txt,.asc'}
            for kind in ['model',*MODEL_ADAPTERS,*ADAPTERS]]


def detect_adapter(path, requested='auto'):
    if requested not in ('auto','model') and requested not in ADAPTERS and requested not in MODEL_ADAPTERS: raise ValueError('Unknown import adapter.')
    with path.open('rb') as source: signature=source.read(8)
    netcdf = signature[:4] in (b'CDF\x01',b'CDF\x02',b'CDF\x05') or signature==b'\x89HDF\r\n\x1a\n'
    container='netcdf' if netcdf else 'text'
    if requested != 'auto':
        if ADAPTER_METADATA.get(requested,{}).get('container','text') != container:
            raise ValueError('This file is not a readable NetCDF file for the selected adapter.' if not netcdf else 'A NetCDF file cannot use a delimited-text adapter.')
        return requested
    meta={'container':container}
    matches=[]
    if netcdf:
        with xr.open_dataset(path, decode_cf=False, create_default_indexes=False) as ds:
            meta.update(attrs=dict(ds.attrs),dimensions=dict(ds.sizes),variables={n:{'dims':list(v.dims),'attrs':dict(v.attrs)} for n,v in ds.variables.items()})
        names=set(meta['variables']); attrs=meta['attrs']
        if {'N_PROF','N_LEVELS'} <= set(meta['dimensions']) and {'PRES','TEMP','PSAL','JULD','PLATFORM_NUMBER'} <= names: matches.append('argo')
        if {'PROFILE','PHASE','TIME','TEMP','PSAL'} <= names and 'IMOS' in str(attrs): matches.append('imos-glider')
        if {'pressure','ctd_temperature','ctd_salinity','expocode'} <= names and 'N_PROF' in meta['dimensions']: matches.append('cchdo-ctd')
        if not matches and str(attrs.get('featureType','')).lower() in ('profile','trajectoryprofile','timeseriesprofile') and any(v['attrs'].get('cf_role')=='profile_id' for v in meta['variables'].values()): matches.append('cf-profile')
    else:
        with path.open(encoding='utf-8-sig') as stream:
            meta['header']=stream.read(8192)
    for kind,detector in ADAPTER_DETECTORS.items():
        if (kind in ADAPTERS or kind in MODEL_ADAPTERS) and ADAPTER_METADATA[kind]['container']==container and detector(meta): matches.append(kind)
    if len(matches)>1: raise ValueError('Ambiguous source format: '+', '.join(matches)+'. Select its adapter explicitly.')
    return matches[0] if matches else ('model' if netcdf else 'csv')


def prepare_import(path, kind, identity, title):
    """Parse without mutating the catalog. Caller owns/cleans an optional Model."""
    kind=detect_adapter(path,kind)
    digest=file_hash(path)
    is_model=kind=='model' or kind in MODEL_ADAPTERS
    report={'kind':kind,'category':'model' if is_model else 'observations','title':title,'sha256':digest,'bytes':path.stat().st_size,'warnings':[], 'adapter_contract':ADAPTER_METADATA.get(kind,{}).get('plugin')}
    if is_model:
        provenance={}
        if kind in MODEL_ADAPTERS:
            raw,provenance=MODEL_ADAPTERS[kind](path)
            if not isinstance(raw,xr.Dataset) or not isinstance(provenance,dict):
                if isinstance(raw,xr.Dataset): raw.close()
                raise ValueError('Model adapter must return an xarray Dataset and provenance dictionary.')
            raw,ds=bound_model(raw)
        else: raw,ds=open_bounded_model(path)
        if 'ocean3d_product_id' in raw.attrs and not provenance.get('product'):
            raw.close();ds.close()
            raise ValueError('Declared derived products must use the derived-cf adapter to retain lineage.')
        model=Model(identity,ds,{'source':'Imported NetCDF','warning':'User supplied data; source metadata retained.',**provenance},source=raw)
        model.provenance.update(title=title,sha256=digest,synthetic=str(raw.attrs.get('synthetic','')).lower()=='true')
        try:
            product=model.provenance.get('product')
            if product:
                if set(ds.data_vars)!=set(product['outputs']): raise ValueError('Normalized fields must exactly match the registered product outputs.')
                report['product']=product
                report['warnings'].append(model.provenance['warning'])
            cat=model.catalog()
            report.update(variables=cat['variables'],shape=cat['shape'],bounds=cat['bounds'],depth_range=[cat['depths'][0],cat['depths'][-1]],time_range=[cat['times'][0],cat['times'][-1]],time_steps=len(cat['times']))
            recognized={n for n,v in raw.data_vars.items() if any(n in m['aliases'] or (m['standard'] and v.attrs.get('standard_name')==m['standard']) for m in VARIABLES.values())}
            ignored=[n for n in raw.data_vars if n not in recognized and raw[n].ndim>=3]
            if ignored: report['warnings'].append('Not ingested as model fields: '+', '.join(ignored)+'. Register a variable definition or source adapter when needed.')
            # Exercise an actual lazy decode before registration, without scanning the complete grid.
            for da in ds.data_vars.values(): da.isel({d:0 for d in da.dims}).load()
            return model,[],report
        except Exception:
            model.close();raise
    profiles=ADAPTERS[kind](path)
    if not isinstance(profiles,list) or not 0<len(profiles)<=10_000: raise ValueError('Adapter must return 1–10,000 profiles.')
    seen=set(); total=0; variables=Counter(); quality=Counter(); warnings=set()
    extent=[180.,90.,-180.,-90.]
    for p in profiles:
        if not isinstance(p.get('id'),str) or not p['id'].strip() or p['id'] in seen: raise ValueError('Profile IDs must be nonempty and unique.')
        seen.add(p['id']);validate_profile(p)
        if p.get('sensor_id'):
            sensor=SENSORS.get(p['sensor_id'])
            if not sensor or p.get('geometry')!=sensor['geometry']: raise ValueError('Sensor output must match a registered geometry.')
            report.setdefault('sensors',{})[sensor['id']]=sensor
        if not p['samples']: raise ValueError('An imported profile contains no depth samples.')
        for row in p['samples']:
            lon=row.get('longitude',p['longitude']); lat=row.get('latitude',p['latitude'])
            extent=[min(extent[0],lon),min(extent[1],lat),max(extent[2],lon),max(extent[3],lat)]
            if row['variable'] not in VARIABLES: raise ValueError('Adapter returned an unregistered variable.')
            value=row['value']
            if value is not None and not np.isfinite(value): raise ValueError('Adapter values must be finite or null.')
            variables[row['variable']]+=1
            quality['missing' if value is None else 'good' if row['qc']==1 else 'probably_good' if row['qc']==2 else 'excluded']+=1
        total+=len(p['samples']);warnings.update(p.get('import_warnings',[]))
        if total>1_000_000: raise ValueError('Adapter output exceeds 1,000,000 variable samples.')
    report.update(profile_count=len(profiles),sample_count=total,variables=[{'id':k,**VARIABLES[k],'samples':v} for k,v in variables.items()],instruments=dict(Counter(p['instrument'] for p in profiles)),qc=dict(quality),warnings=sorted(warnings),depth_range=[min(p['depth_range'][0] for p in profiles),max(p['depth_range'][1] for p in profiles)],time_range=[min(p.get('time_range',[p['time']])[0] for p in profiles),max(p.get('time_range',[p['time']])[-1] for p in profiles)],bounds=[min(p['longitude'] for p in profiles),min(p['latitude'] for p in profiles),max(p['longitude'] for p in profiles),max(p['latitude'] for p in profiles)],profiles=[{'id':p['id'],'instrument':p['instrument'],'time':p['time'],'depth_range':p['depth_range']} for p in profiles[:8]])
    report['bounds']=extent
    return None,profiles,report
