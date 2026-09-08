"""Acquire a reproducible basin-wide HYCOM current case; keep original sources.

Run from the repository root: python -m scripts.bootstrap_currents
The API should be stopped when replacing an already registered dataset.
"""
from datetime import datetime, timezone
import json
import subprocess
import shutil
from urllib.parse import urlencode
import xarray as xr
import numpy as np
from backend.hycom import FOLDER, MODEL_ID, convert_currents, component_fields
from backend.science import Model, file_hash

BASE = 'https://ncss.hycom.org/thredds/ncss/grid/'
RUN = '2026-09-06T12:00:00Z'
METADATA = 'https://tds.hycom.org/thredds/catalog/FMRC_ESPC-D-V02_uv3z/runs/catalog.html?dataset=FMRC_ESPC-D-V02_uv3z/runs/FMRC_ESPC-D-V02_uv3z_RUN_' + RUN
PARAMETERS = dict(north=29.5, south=-29.5, east=119.5, west=30.5, horizStride=12,
    time_start='2026-09-07T12:00:00Z', time_end='2026-09-07T18:00:00Z', timeStride=1, vertStride=1, accept='netcdf')


def acquire(url, path):
    if path.exists():
        return
    part = path.with_suffix('.part')
    try:
        subprocess.run(['curl.exe' if __import__('os').name == 'nt' else 'curl', '--fail', '--silent', '--show-error',
            '--proto', '=https', '--max-time', '150', '--max-filesize', str(32 * 1024 * 1024), '--output', str(part), url], check=True, timeout=155)
        if part.stat().st_size > 32 * 1024 * 1024:
            raise ValueError('HYCOM source exceeds 32 MiB.')
        with xr.open_dataset(part) as raw:
            if not raw.data_vars:
                raise ValueError('Empty HYCOM source.')
            raw.load()
        part.replace(path)
    finally:
        part.unlink(missing_ok=True)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False), encoding='utf-8')


def main():
    FOLDER.mkdir(parents=True, exist_ok=True)
    sources = []
    for kind, variables in [('uv3z', ['water_u', 'water_v']), ('ts3z', ['water_temp', 'salinity'])]:
        collection = 'FMRC_ESPC-D-V02_' + kind
        url = BASE + collection + '/runs/' + collection + '_RUN_' + RUN + '?' + urlencode({'var': variables, **PARAMETERS}, doseq=True)
        path = FOLDER / (kind + '-source.nc')
        acquire(url, path)
        sources.append(dict(file=path.name, url=url, sha256=file_hash(path), bytes=path.stat().st_size,
            variables=variables, selection=PARAMETERS, forecast_run=RUN,
            method='Official NCSS fixed-run NetCDF response. Forecast initialization comes from the explicit THREDDS run identifier; the subset omits run coordinates.',
            retrieved_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(), license='HYCOM catalogue: freely available'))
        print(kind, path.stat().st_size, 'bytes', flush=True)
    with xr.open_dataset(FOLDER / 'uv3z-source.nc') as uv, xr.open_dataset(FOLDER / 'ts3z-source.nc') as ts:
        ds = convert_currents(uv, ts, forecast_run=RUN).load()
        _, runs = component_fields(uv, ts, forecast_run=RUN)
        if len(runs) != 4:
            raise ValueError('Forecast source must identify initialization times for all four components.')
        run_times = [np.datetime_as_string(t, unit='s') + 'Z' for t in runs['water_u']]
        lead_hours = ((ds.time.values - runs['water_u']) / np.timedelta64(1, 'h')).tolist()
        expected = np.array(['2026-09-07T12:00', '2026-09-07T15:00', '2026-09-07T18:00'], dtype='datetime64[ns]')
        if not np.array_equal(ds.time.values, expected) or ds.sizes['depth'] != 40 or ds.depth.values[-1] != 5000:
            raise ValueError('Source did not return all requested times and depths.')
    ds.to_netcdf(FOLDER / 'model.nc')
    provenance = dict(title=ds.attrs['title'], source='FNMOC HYCOM ESPC-D V02, expt_03.1; official NCSS forecast subsets',
        provider='HYCOM', synthetic=False, product_type='forecast_snapshot', sha256=file_hash(FOLDER / 'model.nc'),
        source_sha256=sources[0]['sha256'], source_url=sources[0]['url'], metadata_url=METADATA,
        license='HYCOM catalogue: freely available', retrieved_at=sources[0]['retrieved_at'],
        spatial_resolution='Published GLBy0.08 grid, horizontal stride 12: approximately 0.96° longitude by 0.48° latitude in this subset. All 40 published z levels retained.',
        temporal_resolution='Three 3-hour valid times; 7 September 2026, 12–18 UTC. Forecast leads 24, 27 and 30 hours from 6 September 12 UTC.',
        forecast_reference_times=run_times, forecast_lead_hours=lead_hours,
        forecast_reference_method='Explicit THREDDS fixed-run dataset identifier for both source URLs. NCSS omits forecast_reference_time in this response; template global time_origin is not used.',
        vector_components=['eastward', 'northward'], vertical_velocity_available=False,
        source_download_url=f'/demo/{MODEL_ID}/uv3z-source.nc',
        warning='Preserved model forecast snapshot, not observations or live synchronization. Horizontal components at 40 depths; vertical velocity is not supplied. Missing ocean cells are preserved.',
        transformations=['NCSS horizontal stride 12, vertical stride 1; exact same coordinates, valid times and initialization times required for scalar and vector sources.',
            'Decode source missing values; preserve float32 eastward/northward components without rotation. Equivalent time/time1 coordinate names normalized after exact comparison.',
            'TEOS-10 GSW converts in-situ temperature to potential temperature at 0 dbar using salinity and geographic position.',
            'Original sources and hashes retained. Float32 normalized model; display grids use bounded interpolation.'],
        sources=sources)
    model = Model(MODEL_ID, ds, provenance)
    write(FOLDER / 'case.json', dict(id=MODEL_ID, provenance=provenance, sources=sources))
    public = FOLDER.parents[1] / 'web' / 'public' / 'demo'
    (public / MODEL_ID).mkdir(parents=True, exist_ok=True)
    for item in sources:
        shutil.copyfile(FOLDER / item['file'], public / MODEL_ID / item['file'])
    write(public / MODEL_ID / 'sources.json', provenance)
    catalog = json.loads((public / 'catalog.json').read_text(encoding='utf-8'))
    catalog['models'] = [m for m in catalog['models'] if m['id'] != MODEL_ID] + [model.catalog()]
    write(public / 'catalog.json', catalog)
    for variable in ds.data_vars:
        for index in range(ds.sizes['time']):
            for depth, suffix in [(None, ''), (500, '-upper500')]:
                write(public / MODEL_ID / f'{variable}-{index}{suffix}.json', model.volume(variable, index, maximum_depth=depth))
    print(json.dumps(dict(model=MODEL_ID, shape=dict(ds.sizes), bounds=model.catalog()['bounds'], source_sha256=provenance['source_sha256'])), flush=True)


if __name__ == '__main__':
    main()
