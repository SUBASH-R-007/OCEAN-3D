"""Bounded, provenance-preserving access to the public INCOIS ERDDAP catalogue.

Only IDs/variables/axes in the administrator-acquired catalogue are accepted.
There is no user-supplied URL, code execution, invented time axis or depth axis.
"""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote
import hashlib
import json
import math
import shutil
import subprocess
import threading
import numpy as np
import xarray as xr
from .science import file_hash, Model, normalize, SCIENCE_LOCK

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'data/incois-catalog'
BASE = 'https://erddap.incois.gov.in/erddap'
IO_LOCK = threading.RLock()
CACHE_LIMIT = 512 * 1024 * 1024
CATALOG_REVISIONS = {}
ACTIVE_REVISION = None


def install_catalog(revision, catalog, folder):
    """Publish an immutable, validated catalogue generation in this process."""
    global ACTIVE_REVISION
    CATALOG_REVISIONS[revision] = (catalog, Path(folder))
    ACTIVE_REVISION = revision


def reset_catalog():
    global ACTIVE_REVISION
    ACTIVE_REVISION = None
    CATALOG_REVISIONS.clear()


def acquire(url, path, limit=32*1024*1024, refresh=False):
    if not url.startswith(BASE + '/'):
        raise ValueError('Only the official INCOIS ERDDAP endpoint is allowed.')
    with IO_LOCK:
        if path.exists() and not refresh: return path
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(path.suffix + '.part')
        try:
            curl = shutil.which('curl.exe' if __import__('sys').platform == 'win32' else 'curl')
            if not curl: raise ValueError('The acquisition service requires curl with HTTPS verification.')
            result = subprocess.run([curl, '--fail', '--silent', '--show-error', '--proto', '=https',
                '--max-time', '45', '--max-filesize', str(limit), url, '-o', str(part)],
                capture_output=True, timeout=50)
            if result.returncode:
                raise ValueError('INCOIS did not return this selection within the download limit. Try a smaller region/date selection or retry later.')
            if part.stat().st_size > limit: raise ValueError('Source response exceeds the download budget.')
            if path.suffix == '.nc':
                with SCIENCE_LOCK, xr.open_dataset(part) as ds:
                    if not ds.variables: raise ValueError('Empty source dataset.')
            else:
                json.loads(part.read_text(encoding='utf-8'))
            part.replace(path)
            return path
        finally:
            part.unlink(missing_ok=True)


def read_catalog(revision=None):
    selected = revision or ACTIVE_REVISION
    if selected and selected != 'bundled':
        if selected not in CATALOG_REVISIONS: raise ValueError('Catalogue revision expired; refresh the source library.')
        return CATALOG_REVISIONS[selected][0]
    return json.loads((FOLDER/'catalog.json').read_text(encoding='utf-8'))


def native_values(values):
    return [float(v) if np.isfinite(v) else None for v in np.asarray(values).ravel()]


def product_for(identity, revision=None):
    for p in read_catalog(revision)['products']:
        if p['id'] == identity: return p
    raise ValueError('Unknown INCOIS product.')


def axes_for(product):
    revision=product.get('catalog_revision')
    if revision and revision != 'bundled' and revision not in CATALOG_REVISIONS:
        raise ValueError('Catalogue revision expired; refresh the source library.')
    folder=CATALOG_REVISIONS[revision][1] if revision in CATALOG_REVISIONS else FOLDER
    with SCIENCE_LOCK, xr.open_dataset(folder/(product['id']+'-axes.nc')) as ds:
        return {name: ds[name].values.copy() for name in product['dimensions']}


def build_catalog(refresh=False, folder=None, check_stop=None):
    folder=Path(folder) if folder is not None else FOLDER
    table = json.loads((folder/'catalog-source.json').read_text(encoding='utf-8'))['table']
    products = []
    for row in table['rows']:
        if check_stop: check_stop()
        row = dict(zip(table['columnNames'], row))
        identity = row['Dataset ID']
        if identity == 'allDatasets': continue
        rows = json.loads((folder/(identity+'.json')).read_text(encoding='utf-8'))['table']['rows']
        attrs = {}
        for kind, name, key, _, value in rows:
            if kind == 'attribute': attrs.setdefault(name, {})[key] = value
        dimensions = {r[1]: int(r[4].split('nValues=')[1].split(',')[0]) for r in rows if r[0] == 'dimension'}
        glob = attrs['NC_GLOBAL']
        volume = dimensions.get('ZAX', 0) > 1
        p = dict(id=identity, title=row['Title'], institution=row['Institution'],
                 kind='volume' if volume else ('surface' if dimensions else 'observations'),
                 dimensions=dimensions, metadata_url=f'{BASE}/info/{identity}/index.html',
                 source_url=row['griddap'] or row['tabledap'],
                 start=glob.get('time_coverage_start'), end=glob.get('time_coverage_end'),
                 license=glob.get('license', ''), metadata_sha256=file_hash(folder/(identity+'.json')),
                 variables=[dict(id=r[1], label=attrs.get(r[1], {}).get('long_name', r[1]),
                     units=attrs.get(r[1], {}).get('units', 'Not specified'),
                     dimensions=r[4].split(', ') if dimensions else [],
                     standard_name=attrs.get(r[1], {}).get('standard_name')) for r in rows if r[0]=='variable'])
        p['bounds'] = [float(glob[k]) for k in ('geospatial_lon_min','geospatial_lat_min','geospatial_lon_max','geospatial_lat_max')]
        if dimensions:
            path = acquire(f'{BASE}/griddap/{identity}.nc?'+','.join(dimensions), folder/(identity+'-axes.nc'), 2*1024*1024,refresh=refresh)
            with SCIENCE_LOCK, xr.open_dataset(path) as ds:
                for name, count in dimensions.items():
                    if ds[name].size != count: raise ValueError('Source axis changed; refresh metadata first.')
                    a=ds[name].values
                    if np.any(a[1:] <= a[:-1]): raise ValueError('Expected ascending unique source axes.')
                p['times'] = [np.datetime_as_string(t, unit='s')+'Z' for t in ds.time.values]
                z = next((n for n in dimensions if n not in ('time','latitude','longitude')), None)
                p['vertical_axis'] = dict(name=z, values=ds[z].values.tolist(), units=ds[z].attrs.get('units','')) if z else None
            p['axes_sha256'] = file_hash(path)
        p['note'] = ('Analyzed water-column fields. Temperature convention is unspecified; no density or potential-temperature comparison.' if volume else
            'Individual profiles with source quality flags. Pressure is converted to depth using latitude.' if not dimensions else
            'Surface or diagnostic field. Wind is atmospheric wind, not an underwater current; no invented water-column depths.')
        if identity.endswith('_VAM'): p['note'] += ' Relative-error units are inconsistent with their labels; retained exactly as published, not interpreted as standard deviation.'
        if 'McCreary' in identity:
            for v in p['variables']:
                if v['id'].endswith(('ROIOBS','BOXOBS')):
                    v['source_units']=v['units']; v['units']='count'
            p['note'] += ' Observation-count units corrected from erroneous source salinity units to counts.'
        products.append(p)
    result = dict(schema='ocean3d-incois-catalog-1', retrieved_at=datetime.now(timezone.utc).isoformat(),
                  source_url=BASE+'/info/index.html', source_sha256=file_hash(folder/'catalog-source.json'),
                  scope='All scientific datasets advertised by the public INCOIS ERDDAP at retrieval; other portals and restricted feeds are outside this inventory.', products=products)
    (folder/'catalog.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    return result


def grid_query(product, variables, index, depth=0, bbox=None, resolution=240, volume=False, frames=1, native=False):
    if product['kind'] == 'observations': raise ValueError('This product contains profiles, not a grid.')
    if not variables or any(v not in {v['id'] for v in product['variables']} for v in variables):
        raise ValueError('Variable is not in the source catalogue.')
    axes = axes_for(product)
    if not 0 <= index < len(axes['time']): raise ValueError('Time index unavailable.')
    if not 1 <= frames <= 3 or index-frames+1 < 0: raise ValueError('Choose one to three available frames.')
    if not 16 <= resolution <= 480: raise ValueError('Display resolution must be 16–480.')
    bounds = list(bbox) if bbox is not None else product['bounds']
    if len(bounds)!=4 or not np.isfinite(bounds).all() or bounds[0]>=bounds[2] or bounds[1]>=bounds[3]:
        raise ValueError('Enter an ordered west, south, east, north region in the source longitude convention.')
    slices, sampling = {}, {}
    for name, a in axes.items():
        if name == 'time': slices[name] = f'[{index-frames+1}:1:{index}]'; continue
        if name in ('latitude','longitude'):
            lo,hi = (bounds[1],bounds[3]) if name=='latitude' else (bounds[0],bounds[2])
            if lo < float(a[0])-1e-6 or hi > float(a[-1])+1e-6: raise ValueError('Region exceeds source coverage.')
            found=np.flatnonzero((a >= lo-1e-6)&(a <= hi+1e-6))
            if len(found)<2: raise ValueError('Region must contain at least two native cells per horizontal axis.')
            stride=1 if volume or native else max(1,math.ceil(len(found)/resolution))
            slices[name]=f'[{found[0]}:{stride}:{found[-1]}]'
            sampling[name]=dict(native_cells=len(found),stride=stride,first=float(a[found[0]]),last=float(a[found[-1]]))
        elif volume:
            slices[name]=f'[0:1:{len(a)-1}]'
        else:
            if not 0 <= depth < len(a): raise ValueError('Vertical index unavailable.')
            slices[name]=f'[{depth}]'
    suffix=''.join(slices[name] for name in product['dimensions'])
    query=','.join(v+suffix for v in variables)
    return f'{BASE}/griddap/{product["id"]}.nc?'+quote(query,safe=',:'),sampling


def cached_source(url, revision=None):
    folder=FOLDER/'cache'; folder.mkdir(exist_ok=True)
    with IO_LOCK:
        files=sorted(folder.glob('*.nc'), key=lambda p:p.stat().st_mtime)
        total=sum(p.stat().st_size for p in files)
        for old in files:
            if total <= CACHE_LIMIT-32*1024*1024: break
            total-=old.stat().st_size; old.unlink()
        cache_key=url if not revision else url+'#'+revision
        return acquire(url, folder/(hashlib.sha256(cache_key.encode()).hexdigest()+'.nc'))


def grid_packet(product, variables, index, depth=0, bbox=None, resolution=240):
    url,sampling=grid_query(product,variables,index,depth,bbox,resolution)
    with IO_LOCK:
        path=cached_source(url,product.get('catalog_revision'))
        with SCIENCE_LOCK, xr.open_dataset(path) as ds:
            packet=dict(schema='ocean3d-incois-grid-1', product=product['id'], time=np.datetime_as_string(ds.time.values[0],unit='s')+'Z',
                longitude=ds.longitude.values.tolist(), latitude=ds.latitude.values.tolist(),
                fields={v:native_values(ds[v].squeeze(drop=True).transpose('latitude','longitude').values) for v in variables},
                source_url=url, native_source_url=grid_query(product,variables,index,depth,bbox,resolution,native=True)[0],source_sha256=file_hash(path), retrieved_at=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
                sampling=sampling, vertical_axis=product.get('vertical_axis'), vertical_index=depth)
    return packet


def convert_volume(raw, product):
    from .incois import convert
    if 'McCreary' in product['id']:
        result=convert(raw)
    elif product['id'] in ('incois_argo_mnt_VAM','incois_argo_10d_VAM'):
        if raw.ZAX.attrs.get('units','').lower()!='meters' or raw.TEMP.attrs.get('units')!='degs' or raw.SAL.attrs.get('standard_name')!='sea_water_practical_salinity' or raw.SAL.attrs.get('units')!='PSU':
            raise ValueError('INCOIS VAM metadata changed; review the adapter.')
        ds=raw.rename(ZAX='depth')
        result=xr.Dataset({'analyzed_temperature':ds.TEMP.copy(),'salinity':ds.SAL.copy()})
        result.analyzed_temperature.attrs=dict(units='degree_Celsius',long_name='INCOIS VAM analyzed temperature; thermodynamic convention unspecified')
        result.salinity.attrs=dict(units='1',standard_name='sea_water_salinity')
        result.depth.attrs=dict(units='m',positive='down',standard_name='depth')
        result=normalize(result)
    else: raise ValueError('This product has no supported water-column grid.')
    result.attrs.update(title=product['title']+' · Indian Ocean',synthetic='false')
    return result


def acquire_volume(product, index, frames=1):
    if product['kind']!='volume': raise ValueError('Surface products cannot be extruded into a water column.')
    variables=[v['id'] for v in product['variables']]
    url,_=grid_query(product,variables,index,volume=True,frames=frames)
    with IO_LOCK:
        path=cached_source(url,product.get('catalog_revision'))
        with SCIENCE_LOCK, xr.open_dataset(path) as raw:
            ds=convert_volume(raw,product).load()
            if frames==1:ds.attrs['title']+=' · '+np.datetime_as_string(ds.time.values[0],unit='D')
            provenance=dict(title=ds.attrs['title'],source=product['title'],provider='INCOIS',synthetic=False,
                product_type='objective_analysis',dataset_id=product['id'],source_url=url,metadata_url=product['metadata_url'],
                source_sha256=file_hash(path),sha256=file_hash(path),license=product['license'],
                retrieved_at=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),warning=product['note'],
                spatial_resolution='1° native grid · 24 depths · full 30.5–119.5°E, 29.5°S–29.5°N domain',
                temporal_resolution='Monthly analysis' if '_mnt_' in product['id'] else '10-day analysis',
                temperature_definition='Published analyzed temperature; potential versus in-situ unspecified.',
                transformations=['Full native geographic and depth coverage; source fill values remain missing. No source stride.',
                                 'Surface counts and relative-error fields remain available in the source library.'])
            if 'McCreary' in product['id']:
                from .incois import support_summary
                provenance['support_by_time']=support_summary(raw)
        identity='incois-'+product['id'].removeprefix('incois_argo_').replace('_','-').lower()+('-latest' if frames>1 else '-'+str(index))
        if product.get('catalog_revision'):
            identity='sync-'+hashlib.sha256((product['id']+file_hash(path)).encode()).hexdigest()[:24]
            provenance['catalog_revision']=product['catalog_revision']
        return Model(identity,ds,provenance),path


def load_basin_models():
    path=FOLDER/'volumes.json'
    if not path.exists(): return []
    models=[]
    for item in json.loads(path.read_text(encoding='utf-8')):
        source=FOLDER/item['file']
        if source.parent != FOLDER or file_hash(source)!=item['sha256']: raise ValueError('INCOIS basin manifest checksum mismatch.')
        original=FOLDER/item['source_file']
        if original.parent != FOLDER or file_hash(original)!=item['source_sha256']:raise ValueError('INCOIS original source checksum mismatch.')
        with SCIENCE_LOCK, xr.open_dataset(source) as ds:
            models.append(Model(item['id'],normalize(ds).load(),item['provenance']))
    return models
