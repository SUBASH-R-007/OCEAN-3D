"""Preserve public instrument sources and prepare bounded, native-resolution cases."""
from pathlib import Path
import hashlib
import json
import shutil
import urllib.request
import numpy as np
import xarray as xr
from backend.instrument_sources import load_instrument_cases
from backend.reference import load_reference
from backend.demo import build_demo
from backend.science import file_hash

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'data/instruments'
PUBLIC=ROOT/'web/public/demo/instruments'
SOURCES={
 'glider-original.nc':'https://thredds.aodn.org.au/thredds/fileServer/IMOS/ANFOG/seaglider/Ningaloo20100906/IMOS_ANFOG_BCEOPSTUV_20100906T235814Z_SG152_FV01_timeseries_END-20101019T010134Z.nc',
 'ctd-original.nc':'https://cchdo.ucsd.edu/data/43064/325020250321_ctd.nc',
 'bgc-incois.nc':'https://data-argo.ifremer.fr/dac/incois/2902273/profiles/SD2902273_159.nc',
 'bgc-aoml.nc':'https://data-argo.ifremer.fr/dac/aoml/2903464/profiles/SD2903464_007.nc',
}

def dump(path,value):path.write_text(json.dumps(value,separators=(',',':'),allow_nan=False),encoding='utf-8')

def acquire():
 FOLDER.mkdir(parents=True,exist_ok=True)
 for name,url in SOURCES.items():
  path=FOLDER/name
  if path.exists():continue
  with urllib.request.urlopen(url,timeout=120) as response:content=response.read(64*1024*1024+1)
  if len(content)>64*1024*1024:raise ValueError('Instrument source exceeds the acquisition limit.')
  temporary=path.with_suffix('.part');temporary.write_bytes(content)
  with xr.open_dataset(temporary):pass
  temporary.replace(path)

def main():
 acquire();PUBLIC.mkdir(parents=True,exist_ok=True)
 with xr.open_dataset(FOLDER/'glider-original.nc') as ds:
  ix=np.flatnonzero(np.isin(ds.PROFILE.values,[10,11,12,13]))
  selected=ds.isel(TIME=ix).load()
  selected.attrs['ocean3d_subset']='All native samples of PROFILE 10, 11, 12 and 13. No resampling. Source quality flags and coordinates unchanged.'
  selected.to_netcdf(FOLDER/'glider-native-subset.nc')
 with xr.open_dataset(FOLDER/'ctd-original.nc') as ds:
  selected=ds.isel(N_PROF=[10,40,70,100]).load()
  selected.attrs['ocean3d_subset']='Native N_PROF indices 10, 40, 70 and 100. All native levels retained; no resampling.'
  for variable in selected.variables.values():variable.encoding.pop('char_dim_name',None)
  selected.to_netcdf(FOLDER/'ctd-native-subset.nc')
 items=[]
 for name,adapter,original,metadata in [
  ('glider-native-subset.nc','imos-glider','glider-original.nc','https://research-repository.uwa.edu.au/en/datasets/imos-ocean-gliders-seaglider-deployment-in-western-australia-off--3/'),
  ('ctd-native-subset.nc','cchdo-ctd','ctd-original.nc','https://cchdo.ucsd.edu/cruise/325020250321'),
  ('bgc-incois.nc','argo','bgc-incois.nc',SOURCES['bgc-incois.nc']),
  ('bgc-aoml.nc','argo','bgc-aoml.nc',SOURCES['bgc-aoml.nc']),
 ]:
  shutil.copy2(FOLDER/name,PUBLIC/name)
  item=dict(file=name,adapter=adapter,sha256=file_hash(FOLDER/name),original_source_file=original,original_source_url=SOURCES[original],original_source_sha256=file_hash(FOLDER/original),source_url=metadata,source_download_url='/demo/instruments/'+name)
  if adapter=='argo':item.update(license='CC BY 4.0',acknowledgement='Argo data collected and made freely available by the international Argo Program and national programs. https://doi.org/10.17882/42182. S-profile means merged core/BGC observations, not simulated observations.')
  if adapter=='cchdo-ctd':item.update(acknowledgement='GO-SHIP I09N 2025, R/V Thomas G. Thompson; CTD: Susan Becker and Todd Martz. Cite CCHDO cruise 325020250321 and the original investigators.')
  items.append(item)
 manifest=dict(sources=items,selection='Four consecutive native IMOS casts, four GO-SHIP CTD stations spanning the Indian Ocean, two BGC-Argo casts including INCOIS.')
 dump(FOLDER/'manifest.json',manifest)
 real=load_instrument_cases(force_parse=True)
 dump(FOLDER/'profiles.json',real)
 manifest['normalized']=dict(file='profiles.json',sha256=file_hash(FOLDER/'profiles.json'))
 dump(FOLDER/'manifest.json',manifest)
 model,demo=build_demo();model.close()
 reference=load_reference();other=[]
 if reference:
  model,other=reference;model.close()
 profiles=[*demo,*other,*real]
 index={}
 for p in profiles:
  filename=hashlib.sha256(p['id'].encode()).hexdigest()[:24]+'.json'
  dump(PUBLIC/filename,p);index[p['id']]='/demo/instruments/'+filename
 dump(PUBLIC/'index.json',index)
 catalog_file=ROOT/'web/public/demo/catalog.json'
 catalog=json.loads(catalog_file.read_text(encoding='utf-8'))
 by_id={p['id']:p for p in catalog['profiles']}
 for p in real:
  by_id[p['id']]={**{k:v for k,v in p.items() if k!='samples'},'variables':sorted({r['variable'] for r in p['samples']})}
 catalog['profiles']=list(by_id.values());dump(catalog_file,catalog)
 print(json.dumps([{'id':p['id'],'instrument':p['instrument'],'levels':len({r['depth'] for r in p['samples']}),'variables':{v:sum(r['qc']==1 and r['value'] is not None for r in p['samples'] if r['variable']==v) for v in {r['variable'] for r in p['samples']}}} for p in real],indent=2))

if __name__=='__main__':main()
