"""Verified depth-resolved HYCOM currents, with co-timed scalar fields."""
from pathlib import Path
import json
import numpy as np
import xarray as xr
import gsw
from .science import Model, normalize, file_hash

FOLDER = Path(__file__).resolve().parents[1] / 'data' / 'hycom'
MODEL_ID = 'hycom-currents-indian'


def component_fields(velocity: xr.Dataset, scalars: xr.Dataset, forecast_run=None):
    fields = {}
    runs = {}
    for source, names in [(velocity, ('water_u', 'water_v')), (scalars, ('water_temp', 'salinity'))]:
        for name in names:
            field = source[name]
            if len(field.dims) != 4 or field.dims[1:] != ('depth', 'lat', 'lon'):
                raise ValueError(f'Unexpected HYCOM {name} dimensions.')
            time_dim = field.dims[0]
            if time_dim != 'time' and field[time_dim].attrs.get('standard_name') != 'time':
                raise ValueError(f'Unexpected HYCOM {name} time coordinate.')
            fields[name] = field.rename({time_dim: 'time'}) if time_dim != 'time' else field
            if time_dim + '_run' in source:
                runs[name] = source[time_dim + '_run'].values
            else:
                references = [c for c in field.coords.values() if c.attrs.get('standard_name') == 'forecast_reference_time']
                if len(references) == 1:
                    reference = references[0]
                    if reference.ndim == 0:
                        runs[name] = np.repeat(reference.values, field.sizes[time_dim])
                    elif reference.dims == (time_dim,):
                        runs[name] = reference.values
            if forecast_run is not None:
                declared = np.repeat(np.datetime64(forecast_run.removesuffix('Z'), 'ns'), field.sizes[time_dim])
                if name in runs and not np.array_equal(runs[name], declared):
                    raise ValueError('Source forecast initialization differs from the requested fixed run.')
                runs[name] = declared
    first = fields['water_u']
    for field in fields.values():
        for coordinate in ('time', 'depth', 'lat', 'lon'):
            if not np.array_equal(first[coordinate].values, field[coordinate].values):
                raise ValueError(f'HYCOM component/scalar {coordinate} coordinates differ.')
    if runs and (len(runs) != 4 or any(not np.array_equal(runs['water_u'], run) for run in runs.values())):
        raise ValueError('HYCOM component/scalar forecast initialization times differ or are missing.')
    return fields, runs


def convert_currents(velocity: xr.Dataset, scalars: xr.Dataset, forecast_run=None) -> xr.Dataset:
    """Reject incompatible grids rather than silently joining or rotating vectors."""
    fields, _ = component_fields(velocity, scalars, forecast_run)
    expected = {
        'water_u': ('eastward_sea_water_velocity', ('m/s',)),
        'water_v': ('northward_sea_water_velocity', ('m/s',)),
        'water_temp': ('sea_water_temperature', ('degC', 'degree_Celsius', 'degrees_Celsius')),
        'salinity': ('sea_water_salinity', ('psu', 'PSU', '1', '1e-3')),
    }
    for name, (standard, units) in expected.items():
        field = fields[name]
        if field.attrs.get('standard_name') != standard or field.attrs.get('units') not in units:
            raise ValueError(f'Unexpected HYCOM {name} definition or units.')
        if field.dims != ('time', 'depth', 'lat', 'lon'):
            raise ValueError(f'Unexpected HYCOM {name} dimensions.')
    if velocity.depth.attrs.get('units') != 'm' or velocity.depth.attrs.get('positive') != 'down':
        raise ValueError('HYCOM depths must be metres positive down.')
    pressure = gsw.p_from_z(-scalars.depth.values[:, None, None], scalars.lat.values[None, :, None])
    salt = fields['salinity'].values
    absolute = gsw.SA_from_SP(salt, pressure[None], scalars.lon.values[None, None, None, :], scalars.lat.values[None, None, :, None])
    potential = gsw.pt0_from_t(absolute, fields['water_temp'].values, pressure[None])
    dims = ('time', 'depth', 'latitude', 'longitude')
    ds = xr.Dataset({
        'thetao': (dims, potential, dict(units='degree_Celsius', standard_name='sea_water_potential_temperature')),
        'so': (dims, salt, dict(units='1', standard_name='sea_water_salinity')),
        'uo': (dims, fields['water_u'].values, dict(units='m/s', standard_name='eastward_sea_water_velocity')),
        'vo': (dims, fields['water_v'].values, dict(units='m/s', standard_name='northward_sea_water_velocity')),
    }, coords={
        'time': ('time', fields['water_u'].time.values, dict(standard_name='time')),
        'depth': ('depth', scalars.depth.values, dict(units='m', positive='down', standard_name='depth')),
        'latitude': ('latitude', scalars.lat.values, dict(units='degrees_north', standard_name='latitude')),
        'longitude': ('longitude', scalars.lon.values, dict(units='degrees_east', standard_name='longitude')),
    }, attrs=dict(Conventions='CF-1.10', synthetic='false', title='HYCOM currents · Indian Ocean · 7 September 2026'))
    return normalize(ds)


def load_currents(folder=FOLDER):
    manifest = folder / 'case.json'
    if not manifest.is_file():
        return None
    info = json.loads(manifest.read_text(encoding='utf-8'))
    for item in [dict(file='model.nc', sha256=info['provenance']['sha256']), *info['sources']]:
        path = folder / item['file']
        if path.resolve().parent != folder.resolve() or file_hash(path) != item['sha256']:
            raise ValueError('HYCOM current source checksum or path differs from its manifest.')
    with xr.open_dataset(folder / 'model.nc') as source:
        ds = normalize(source).load()
    return Model(MODEL_ID, ds, info['provenance'])
