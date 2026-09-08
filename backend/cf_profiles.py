"""CF discrete sampling geometry adapters. No inferred QC or temperature convention."""
from pathlib import Path
import numpy as np
import xarray as xr
import gsw
from .science import VARIABLES


def parse_cf_profiles(path: Path):
    from .observations import text, validate_profile
    with xr.open_dataset(path) as ds:
        feature = str(ds.attrs.get('featureType', '')).lower()
        if feature not in ('profile', 'trajectoryprofile', 'timeseriesprofile'):
            raise ValueError('CF observation import requires featureType=profile, trajectoryProfile or timeSeriesProfile.')
        ids = [v for v in ds.variables if ds[v].attrs.get('cf_role') == 'profile_id']
        if len(ids) != 1 or ds[ids[0]].ndim != 1:
            raise ValueError('Provide one one-dimensional cf_role=profile_id variable.')
        profile_dim = ds[ids[0]].dims[0]
        n = ds.sizes[profile_dim]
        if not 0 < n <= 10_000:
            raise ValueError('Import requires 1–10,000 profiles.')
        def coord(standard):
            names = [v for v in ds.variables if ds[v].attrs.get('standard_name') == standard]
            if len(names) != 1:
                raise ValueError(f'Expected one CF {standard} variable.')
            return ds[names[0]]
        lon, lat, time, depth = [coord(k) for k in ('longitude', 'latitude', 'time', 'depth')]
        if any(v.dims != (profile_dim,) for v in (lon, lat, time)):
            raise ValueError('Each profile requires one longitude, latitude and timestamp; sample-varying positions require a dedicated adapter.')
        if not np.issubdtype(time.dtype, np.datetime64) or np.isnat(time.values).any():
            raise ValueError('Profile time must decode to finite Gregorian timestamps.')
        if lon.attrs.get('units') not in ('degrees_east', 'degree_east') or lat.attrs.get('units') not in ('degrees_north', 'degree_north'):
            raise ValueError('Longitude/latitude require degrees_east/degrees_north units.')
        factor = {'m': 1, 'km': 1000}.get(depth.attrs.get('units'))
        if factor is None or depth.attrs.get('positive') not in ('down', 'up'):
            raise ValueError('Depth requires m/km units and positive=up/down.')
        factor *= -1 if depth.attrs['positive'] == 'up' else 1
        counts = [v for v in ds.variables if 'sample_dimension' in ds[v].attrs and ds[v].dims == (profile_dim,)]
        indexers = [v for v in ds.variables if ds[v].attrs.get('instance_dimension') == profile_dim]
        if counts and indexers:
            raise ValueError('Ambiguous ragged profile representation.')
        selectors = []
        if counts:
            if len(counts) != 1:
                raise ValueError('Ambiguous row-size variable.')
            cv = ds[counts[0]]; dim = cv.attrs['sample_dimension']; sizes = cv.values
            if dim not in ds.dims or not np.isfinite(sizes).all() or np.any(sizes < 0) or np.any(sizes != np.floor(sizes)) or int(sizes.sum()) != ds.sizes[dim]:
                raise ValueError('Ragged row sizes must be nonnegative integers summing to the sample dimension.')
            edges = np.r_[0, np.cumsum(sizes).astype(int)]
            selectors = [{dim: slice(int(edges[i]), int(edges[i+1]))} for i in range(n)]
        elif indexers:
            if len(indexers) != 1 or ds[indexers[0]].ndim != 1:
                raise ValueError('Ambiguous profile index variable.')
            ix = ds[indexers[0]]; dim = ix.dims[0]; values = ix.values
            if not np.isfinite(values).all() or np.any(values != np.floor(values)) or np.any(values < 0) or np.any(values >= n):
                raise ValueError('CF profile indices must be zero-based integers within the profile dimension.')
            selectors = [{dim: np.flatnonzero(values == i)} for i in range(n)]
        elif depth.ndim == 2 and depth.dims[0] == profile_dim:
            dim = depth.dims[1]
            selectors = [{profile_dim: i} for i in range(n)]
        elif depth.ndim == 1 and depth.dims[0] != profile_dim:
            dim = depth.dims[0]
            selectors = [{profile_dim: i} for i in range(n)]
        else:
            raise ValueError('Supported CF layouts: orthogonal/incomplete profile arrays, contiguous or indexed ragged profiles.')
        if depth.size > 200_000 or (depth.ndim == 1 and not (counts or indexers) and depth.size * n > 200_000):
            raise ValueError('Import exceeds 200,000 depth samples.')
        variables = []
        in_situ = False
        for key, meta in VARIABLES.items():
            standards = [meta['standard']] if meta['standard'] else []
            if key == 'temperature': standards.append('sea_water_temperature')
            names = [v for v in ds.data_vars if ds[v].attrs.get('standard_name') in standards]
            if len(names) > 1:
                raise ValueError(f'Ambiguous {key} variables.')
            if not names: continue
            da = ds[names[0]]
            if key == 'temperature': in_situ = da.attrs.get('standard_name') == 'sea_water_temperature'
            if set(da.dims) != ({dim} if counts or indexers else {profile_dim, dim}):
                raise ValueError(f'{key} dimensions do not match the profile representation.')
            unit = da.attrs.get('units', '').lower().replace(' ', '')
            units = {'temperature': {'degree_celsius', 'degrees_celsius', 'degc', '°c'}, 'salinity': {'1', 'psu', '1e-3'}, 'chlorophyll': {'mgm-3', 'mg/m3', 'mg/m³'}, 'u': {'ms-1', 'm/s'}, 'v': {'ms-1', 'm/s'}}
            if unit not in units.get(key, set(meta.get('unit_aliases', []))):
                raise ValueError(f'{key}: convert to the documented canonical units before CF observation import.')
            ancillary = str(da.attrs.get('ancillary_variables', '')).split()
            flags = [v for v in ancillary if v in ds and 'flag_meanings' in ds[v].attrs]
            if len(flags) > 1: raise ValueError(f'{key}: ambiguous quality flags.')
            flag = ds[flags[0]] if flags else None
            mapping = {}
            if flag is not None:
                meanings = flag.attrs['flag_meanings'].split(); fv = np.asarray(flag.attrs.get('flag_values', [])).ravel()
                if flag.dims != da.dims or len(meanings) != len(fv) or len(set(fv.tolist())) != len(fv):
                    raise ValueError(f'{key}: quality flag metadata/dimensions do not match.')
                for value, meaning in zip(fv, meanings):
                    mapping[float(value)] = {'good_data': 1, 'good': 1, 'probably_good_data': 2, 'probably_good': 2, 'bad_data': 4, 'bad': 4, 'missing_data': 9, 'missing': 9}.get(meaning, 0)
            variables.append((key, da, flag, mapping))
        if not variables:
            raise ValueError('No supported CF variables. Temperature must explicitly be sea_water_potential_temperature; in-situ temperature is not silently reinterpreted.')
        if in_situ and not any(v[0] == 'salinity' for v in variables):
            raise ValueError('In-situ temperature conversion requires colocated practical salinity.')
        trajectory = None
        if feature in ('trajectoryprofile', 'timeseriesprofile'):
            role = 'trajectory_id' if feature == 'trajectoryprofile' else 'timeseries_id'
            parent_ids = [v for v in ds.variables if ds[v].attrs.get('cf_role') == role]
            if len(parent_ids) != 1 or ds[parent_ids[0]].ndim != 1:
                raise ValueError(f'Provide one one-dimensional cf_role={role} variable.')
            parent = ds[parent_ids[0]]
            indices = [v for v in ds.variables if ds[v].attrs.get('instance_dimension') == parent.dims[0] and ds[v].dims == (profile_dim,)]
            if len(indices) != 1: raise ValueError('Provide a CF profile-to-platform index.')
            pi = ds[indices[0]].values
            if not np.isfinite(pi).all() or np.any(pi != np.floor(pi)) or np.any(pi < 0) or np.any(pi >= parent.size):
                raise ValueError('Invalid profile-to-platform index.')
            trajectory = [text(parent.values[int(j)]) for j in pi]
        output = []; seen = set()
        for i, selector in enumerate(selectors):
            pid = text(ds[ids[0]].values[i])
            if not pid or pid in seen: raise ValueError('Profile IDs must be nonempty and unique.')
            seen.add(pid)
            z = np.asarray(depth.isel({k: v for k, v in selector.items() if k in depth.dims}).values).ravel() * factor
            samples = []
            native = {}; quality_flags = {}
            for key, da, flag, mapping in variables:
                vals = np.asarray(da.isel(selector).values).ravel()
                q = np.asarray(flag.isel(selector).values).ravel() if flag is not None else np.full(vals.size, np.nan)
                if len(z) != len(vals): raise ValueError('Depth and variable sample counts differ.')
                native[key] = vals
                quality_flags[key] = np.array([mapping.get(float(quality), 0) for quality in q])
            converted = dict(native)
            if in_situ:
                pressure = gsw.p_from_z(-z, float(lat[i]))
                salinity = np.where(native['salinity'] >= 0, native['salinity'], np.nan)
                absolute = gsw.SA_from_SP(salinity, pressure, float(lon[i]), float(lat[i]))
                converted['temperature'] = gsw.pt0_from_t(absolute, native['temperature'], pressure)
                tq, sq = quality_flags['temperature'], quality_flags['salinity']
                quality_flags['temperature'] = np.where((tq == 0) | (sq == 0), 0, np.maximum(tq, sq))
            for key, vals in converted.items():
                for j, (zz, value, quality) in enumerate(zip(z, vals, quality_flags[key])):
                    if not np.isfinite(zz): continue
                    row = dict(depth=float(zz), variable=key, value=float(value) if np.isfinite(value) else None, qc=int(quality), adjusted=False, error=None)
                    if in_situ and key == 'temperature': row['source_in_situ_temperature'] = float(native[key][j]) if np.isfinite(native[key][j]) else None
                    samples.append(row)
            if not samples: continue
            p = dict(id=pid, instrument=str(ds.attrs.get('instrument', 'Glider' if feature == 'trajectoryprofile' else 'CTD')), longitude=float(lon[i]), latitude=float(lat[i]), time=np.datetime_as_string(time.values[i], unit='us')+'Z', data_mode='unknown', source='CF DSG: '+path.name, synthetic=str(ds.attrs.get('synthetic', 'false')).lower() == 'true', samples=samples, warning='CF quality meanings mapped explicitly; missing/unknown quality is QC 0. One position and timestamp per cast.', feature_type=feature)
            if trajectory: p['trajectory_id'] = trajectory[i]
            if in_situ: p['conversion'] = 'GSW: depth/latitude to pressure; SP to SA; in-situ Celsius to potential temperature at 0 dbar. Temperature QC combines temperature and salinity; source in-situ values retained; no error propagation.'
            output.append(validate_profile(p))
        if not output: raise ValueError('No finite-depth profiles found.')
        return output
