"""Reproduce a small, source-backed Indian Ocean case without credentials.

The two source files bracket a real Argo cast in space and time. The result
demonstrates ingestion/collocation, not independent model validation.
"""
from pathlib import Path
from urllib.request import urlopen
from datetime import datetime, timezone
import json
import numpy as np
import xarray as xr
import gsw
from backend.science import normalize, file_hash, Model
from backend.observations import parse_argo
from backend.analysis import compare

ROOT=Path(__file__).resolve().parents[1]
ARGO='https://argo-gdac-sandbox.s3.eu-west-3.amazonaws.com/pub/dac/aoml/5904729/profiles/D5904729_274.nc'
REJECTED='https://argo-gdac-sandbox.s3.eu-west-3.amazonaws.com/pub/dac/aoml/2902394/profiles/D2902394_290.nc'
HYCOM='https://ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/ts3z/2023?var=water_temp&var=salinity&north=3.5&south=2.5&east=87&west=86&horizStride=2&time_start=2023-09-01T15%3A00%3A00Z&time_end=2023-09-01T18%3A00%3A00Z&timeStride=1&vertStride=2&accept=netcdf'


def acquire(url, path):
    if path.exists():
        return
    with urlopen(url, timeout=60) as response:
        content=response.read(5*1024*1024+1)
        if len(content)>5*1024*1024:
            raise ValueError('Reference file exceeds the bounded 5 MiB download.')
    # Validate NetCDF before preserving it as a reusable input.
    import io
    with xr.open_dataset(io.BytesIO(content)) as ds:
        if not ds.data_vars: raise ValueError('Empty reference dataset.')
    path.write_bytes(content)


def main():
    folder=ROOT/'data'/'reference';folder.mkdir(parents=True,exist_ok=True)
    argo=folder/'D5904729_274.nc';source=folder/'hycom-indian-source.nc'
    acquire(ARGO,argo);acquire(HYCOM,source)
    profiles=parse_argo(argo)
    with xr.open_dataset(source) as raw:
        # HYCOM explicitly supplies in-situ temperature. Convert thermodynamic
        # definitions using salinity, geographic position and sea pressure.
        if raw.water_temp.attrs.get('standard_name')!='sea_water_temperature':
            raise ValueError('Unexpected source temperature definition.')
        if raw.water_temp.attrs.get('units') not in ('degC','degree_Celsius','degrees_Celsius'):
            raise ValueError('Unexpected source temperature unit.')
        pressure=gsw.p_from_z(-raw.depth.values[:,None,None],raw.lat.values[None,:,None])
        sal=raw.salinity.transpose('time','depth','lat','lon').values
        temperature=raw.water_temp.transpose('time','depth','lat','lon').values
        sa=gsw.SA_from_SP(sal,pressure[None,:,:,:],raw.lon.values[None,None,None,:],raw.lat.values[None,None,:,None])
        potential=gsw.pt0_from_t(sa,temperature,pressure[None,:,:,:])
        converted=xr.Dataset({
            'thetao':(('time','depth','latitude','longitude'),potential,dict(units='degree_Celsius',standard_name='sea_water_potential_temperature')),
            'so':(('time','depth','latitude','longitude'),sal,dict(units='1',standard_name='sea_water_salinity')),
        },coords={'time':raw.time.values,'depth':('depth',raw.depth.values,dict(units='m',positive='down')),
                  'longitude':raw.lon.values,'latitude':raw.lat.values},
           attrs=dict(Conventions='CF-1.10',title='HYCOM / Argo · September 2023',synthetic='false',
                      history='Downloaded bounded HYCOM NCSS subset; decoded scale/fill; TEOS-10 in-situ temperature to potential temperature at 0 dbar.'))
        converted.longitude.attrs=dict(units='degrees_east',standard_name='longitude')
        converted.latitude.attrs=dict(units='degrees_north',standard_name='latitude')
        converted.time.attrs=dict(standard_name='time')
        converted.to_netcdf(folder/'model.nc')
    provenance=dict(title='HYCOM / Argo · September 2023',source='NRL HYCOM GOFS 3.1 + NCODA, experiment 93.0; official NCSS subset',
        synthetic=False,sha256=file_hash(folder/'model.nc'),source_sha256=file_hash(source),
        source_url=HYCOM,license='HYCOM catalog: freely available',
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        warning='Historical analysis, not a forecast. One real Argo cast is a reproducibility case; assimilation status is unknown.',
        transformations=['Server spatial stride 2 and vertical stride 2; two 3-hour analysis timestamps.',
                         'Decode NetCDF scale, offset and missing values.',
                         'GSW p_from_z, SA_from_SP and pt0_from_t; preserve practical salinity.'])
    for p in profiles:
        p.update(sha256=file_hash(argo),source_url=ARGO,license='CC BY 4.0',doi='10.17882/42182')
    rejected_path=folder/'D2902394_290.nc';acquire(REJECTED,rejected_path)
    rejected=parse_argo(rejected_path)
    for p in rejected:
        p.update(sha256=file_hash(rejected_path),source_url=REJECTED,license='CC BY 4.0',doi='10.17882/42182',warning='Adjusted salinity is missing with QC4. Thermodynamic conversion is unsupported; the original temperature sensor flags alone are insufficient.')
    profiles.extend(rejected)
    model=Model('reference-indian',normalize(converted),provenance)
    info=dict(id=model.id,provenance=provenance,profiles=profiles,
              sources=[dict(url=ARGO,sha256=file_hash(argo),bytes=argo.stat().st_size,license='CC BY 4.0',doi='10.17882/42182'),
                       dict(url=HYCOM,sha256=file_hash(source),bytes=source.stat().st_size,license='Freely available')],
              verification={v:compare(model,profiles[0],v)['metrics'] for v in ('temperature','salinity')})
    (folder/'case.json').write_text(json.dumps(info,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(model=model.catalog(),profile={k:v for k,v in profiles[0].items() if k!='samples'},verification=info['verification']),indent=2))


if __name__=='__main__': main()
