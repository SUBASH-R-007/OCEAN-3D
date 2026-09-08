"""Prepare all public gridded products and full-domain water-column snapshots.

Historical dates remain exact, catalogue-indexed, on-demand requests. This does
not download the entire multidecade archive or pretend old products are live.
"""
import json
import sys
import hashlib
import shutil
from pathlib import Path
import numpy as np
import xarray as xr
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.incois_catalog import read_catalog, grid_packet, acquire_volume, FOLDER, native_values
from backend.science import file_hash, clean


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,separators=(',',':'),allow_nan=False),encoding='utf-8')


def main():
    if '--refresh' in sys.argv:
        from scripts.inventory_incois import inventory
        from backend.incois_catalog import build_catalog
        inventory(refresh=True);build_catalog(refresh=True)
        # This explicit administrator operation requires the API to be stopped.
        # Evict only generated request-cache files; preserved source snapshots stay.
        for name,pattern in [('cache','*.nc'),('tables','*.json')]:
            for path in (FOLDER/name).glob(pattern):
                if path.resolve().parent != (FOLDER/name).resolve():raise ValueError('Cache entry escapes its directory.')
                path.unlink()
    catalog=read_catalog(); public=ROOT/'web/public/incois'; manifests=[]
    demo_path=ROOT/'web/public/demo/catalog.json'
    demo=json.loads(demo_path.read_text(encoding='utf-8'))
    for p in catalog['products']:
        if p['kind']=='observations':
            from backend.incois_observations import observation_packet
            try:
                packet=observation_packet(p['end'][:10]+'T00:00:00Z',p['end'])
                target=public/(p['id']+'.json');write(target,packet)
                write(FOLDER/'snapshots'/target.name,packet)
                p['snapshot']=dict(path='/incois/'+target.name,time=p['end'],sha256=file_hash(target))
                p['status']='snapshot_available'
                print(p['id'],len(packet['profiles']),'profiles',flush=True)
            except ValueError as exc:
                p['status']='source_unavailable';p['error']=str(exc)
            continue
        target=public/(p['id']+'.json')
        try:
            write(target,grid_packet(p,[v['id'] for v in p['variables']],len(p['times'])-1))
            packet=json.loads(target.read_text(encoding='utf-8'))
            permanent=FOLDER/'snapshots'/(p['id']+'.nc');permanent.parent.mkdir(exist_ok=True)
            shutil.copyfile(FOLDER/'cache'/(hashlib.sha256(packet['source_url'].encode()).hexdigest()+'.nc'),permanent)
            p['snapshot']=dict(path='/incois/'+target.name,time=packet['time'],sha256=file_hash(target),
                               finite_values={k:sum(v is not None for v in a) for k,a in packet['fields'].items()})
            p['status']='snapshot_available'
            print(p['id'],p['snapshot']['finite_values'],flush=True)
        except ValueError as exc:
            p['status']='source_unavailable';p['error']=str(exc);print(p['id'],str(exc),flush=True)
        if p['kind']!='volume': continue
        model,raw_path=acquire_volume(p,len(p['times'])-1,3)
        preserved=FOLDER/(model.id+'-source.nc');shutil.copyfile(raw_path,preserved)
        model_path=FOLDER/(model.id+'.nc');model.ds.to_netcdf(model_path)
        manifests.append(dict(id=model.id,file=model_path.name,sha256=file_hash(model_path),source_file=preserved.name,source_sha256=file_hash(preserved),provenance=model.provenance))
        p['model_id']=model.id
        demo['models']=[m for m in demo['models'] if m['id']!=model.id]
        demo['models'].insert(0,model.catalog())
        folder=ROOT/'web/public/demo'/model.id
        for variable in model.ds.data_vars:
            for i in range(3):
                for upper,suffix in ((None,''),(500,'-upper500')):
                    write(folder/f'{variable}-{i}{suffix}.json',model.volume(variable,i,maximum_depth=upper))
        if p['id']=='incois_argo_mnt_McCreary':
            with xr.open_dataset(raw_path) as source:
                packet=dict(schema='ocean3d-thermal-atlas-1',provenance=model.provenance,
                    longitude=source.longitude.values.tolist(),latitude=source.latitude.values.tolist(),depth=source.ZAX.values.tolist(),
                    frames=[dict(time=np.datetime_as_string(t,unit='s')+'Z',temperature=native_values(source.T_ANALYZED.isel(time=i).values),
                        local_count=native_values(source.T_BOXOBS.isel(time=i).values),influence_count=native_values(source.T_ROIOBS.isel(time=i).values))
                        for i,t in enumerate(source.time.values)],
                    method='Native INCOIS analyzed temperature; no spatial or temporal interpolation. First downward crossing with continuous finite support and adjacent depth gaps <=150 m. Only the two native bracket levels are interpolated; differences are analyzed structure, not tracked motion.')
            write(folder/'thermal-structure.json',packet)
        print('3D',model.id,dict(model.ds.sizes),flush=True)
    # Make basin-wide monthly coverage the first choice, while keeping old evidence cases reproducible.
    demo['models'].sort(key=lambda m:0 if m['id']=='incois-mnt-mccreary-latest' else 1)
    write(FOLDER/'volumes.json',manifests);write(demo_path,demo)
    write(FOLDER/'catalog.json',catalog);write(public/'catalog.json',catalog)


if __name__=='__main__':main()
