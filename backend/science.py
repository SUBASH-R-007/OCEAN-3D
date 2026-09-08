"""Coordinate-safe bounded sampling. Never extrapolate or replace missing ocean cells."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import threading
from pathlib import Path
import numpy as np
import xarray as xr
from itertools import product

# The NetCDF C libraries and lazy file-backed scientific reads share one process lock.
SCIENCE_LOCK = threading.RLock()

VARIABLES = {
    'temperature': dict(label='Potential temperature', unit='°C', standard='sea_water_potential_temperature', aliases=['thetao', 'temperature'], range=[5, 31]),
    'salinity': dict(label='Practical salinity', unit='PSU', standard='sea_water_salinity', aliases=['so', 'salinity'], range=[32, 36]),
    'u': dict(label='Eastward current', unit='m/s', standard='eastward_sea_water_velocity', aliases=['uo', 'u'], range=[-1, 1]),
    'v': dict(label='Northward current', unit='m/s', standard='northward_sea_water_velocity', aliases=['vo', 'v'], range=[-1, 1]),
    'chlorophyll': dict(label='Chlorophyll', unit='mg/m³', standard='mass_concentration_of_chlorophyll_a_in_sea_water', aliases=['chl', 'chlorophyll'], range=[0.01, 2]),
    'analyzed_temperature': dict(label='Analyzed temperature', unit='°C', standard=None, aliases=['analyzed_temperature'], range=[2, 32]),
    'temperature_spread': dict(label='Temperature spread', unit='°C', standard=None, aliases=['temperature_spread'], range=[0, 4]),
}
COORDS = {'longitude': ['longitude', 'lon'], 'latitude': ['latitude', 'lat'], 'depth': ['depth', 'deptht', 'lev'], 'time': ['time']}


def multilinear(axes, values, queries):
    """Bounded N-D interpolation; only positive-weight corners contribute.

    Unlike a naive weighted sum, 0 * NaN must not erase an exact wet node.
    Any missing corner with a nonzero weight still invalidates the result.
    Singleton axes support their exact coordinate only, without extrapolation.
    """
    q = np.asarray(queries, dtype=float)
    out = np.zeros(len(q), dtype=float)
    valid = np.isfinite(q).all(axis=1)
    lows, highs, fractions = [], [], []
    for d, axis in enumerate(axes):
        axis = np.asarray(axis, dtype=float)
        valid &= (q[:, d] >= axis[0]) & (q[:, d] <= axis[-1])
        if len(axis) == 1:
            low = high = np.zeros(len(q), dtype=int)
            fraction = np.zeros(len(q))
        else:
            high = np.clip(np.searchsorted(axis, q[:, d], side='right'), 1, len(axis)-1)
            low = high-1
            fraction = (q[:, d]-axis[low])/(axis[high]-axis[low])
        lows.append(low); highs.append(high); fractions.append(fraction)
    for corner in product((0, 1), repeat=len(axes)):
        weight = np.ones(len(q))
        indices = []
        for d, side in enumerate(corner):
            weight *= fractions[d] if side else (1-fractions[d])
            indices.append(highs[d] if side else lows[d])
        contributes = (weight > 0) & valid
        vals = values[tuple(indices)]
        valid &= ~contributes | np.isfinite(vals)
        out += np.where(contributes & np.isfinite(vals), weight*np.nan_to_num(vals), 0)
    out[~valid] = np.nan
    return out

def clean(values, decimals=5):
    a = np.asarray(values)
    return np.where(np.isfinite(a), np.round(a, decimals), None).tolist()

def normalize(ds: xr.Dataset) -> xr.Dataset:
    rename = {}
    for target, aliases in COORDS.items():
        candidates = [n for n in ds.variables if n in aliases or ds[n].attrs.get('standard_name') == target]
        if len(candidates) != 1:
            raise ValueError(f'Expected one {target} coordinate; found {candidates}. Use a rectilinear CF grid.')
        if candidates[0] != target:
            rename[candidates[0]] = target
        ds = ds.set_coords(candidates[0])
    ds = ds.rename(rename)
    # CF auxiliary coordinates may be longitude(x), latitude(y), depth(z), time(t).
    # Swap the index dimensions only; this is not regridding or resampling.
    dimension_map = {}
    for name in COORDS:
        if ds[name].ndim != 1:
            raise ValueError(f'{name}: only one-dimensional rectilinear coordinates are supported. Regrid curvilinear/sigma grids first.')
        dim = ds[name].dims[0]
        if dim in dimension_map:
            raise ValueError('Model coordinates must use four distinct rectilinear dimensions.')
        dimension_map[dim] = name
    ds = ds.swap_dims({dim:name for dim,name in dimension_map.items() if dim != name})
    for name, accepted in [('longitude',('degrees_east','degree_east','degrees_E','degree_E')),('latitude',('degrees_north','degree_north','degrees_N','degree_N'))]:
        unit=ds[name].attrs.get('units')
        if unit and unit not in accepted:
            raise ValueError(f'{name}: geographic coordinates require angular degree units; projected/metre coordinates need a dedicated adapter.')
    for name in COORDS:
        if ds[name].ndim != 1 or ds[name].dims != (name,):
            raise ValueError(f'{name}: only one-dimensional rectilinear coordinates are supported. Regrid curvilinear/sigma grids first.')
        if ds[name].size < (1 if name == 'time' else 2):
            raise ValueError(f'{name} requires at least two coordinates for bounded linear interpolation.')
        if ds[name].size > 100_000:
            raise ValueError(f'{name}: coordinate length exceeds the 100,000-element catalog limit.')
    unit = ds.depth.attrs.get('units', '').lower()
    factor = {'m': 1, 'meter': 1, 'meters': 1, 'metres': 1, 'metre': 1, 'km': 1000}.get(unit)
    if factor is None:
        raise ValueError('Model depth must explicitly use metres or kilometres. Pressure and sigma grids require a dedicated adapter.')
    sign = ds.depth.attrs.get('positive', 'down').lower()
    if sign not in ('up', 'down'):
        raise ValueError('Depth positive attribute must be up or down.')
    ds = ds.assign_coords(depth=ds.depth * factor * (-1 if sign == 'up' else 1))
    ds.depth.attrs = {'units': 'm', 'positive': 'down', 'standard_name': 'depth'}
    ds = ds.assign_coords(longitude=((ds.longitude + 180) % 360) - 180)
    if not np.issubdtype(ds.time.dtype, np.datetime64):
        raise ValueError('Only decoded Gregorian/standard calendar timestamps are supported.')
    for name in COORDS:
        ds = ds.sortby(name)
        v = ds[name].values
        if (np.isnat(v).any() if name == 'time' else not np.isfinite(v).all()) or np.any(v[1:] <= v[:-1]):
            raise ValueError(f'{name} coordinates must be finite, unique and monotonic.')
    if ds.depth.min() < 0 or ds.latitude.min() < -90 or ds.latitude.max() > 90:
        raise ValueError('Invalid depth or latitude coordinates.')
    if float(ds.longitude.max() - ds.longitude.min()) > 180:
        raise ValueError('Regional domain must not cross the longitude seam or span more than 180 degrees; subset upstream.')
    found = {}
    for key, meta in VARIABLES.items():
        candidates = [n for n in ds.data_vars if n in meta['aliases'] or (meta['standard'] is not None and ds[n].attrs.get('standard_name') == meta['standard'])]
        if not candidates:
            continue
        if len(candidates) > 1:
            raise ValueError(f'Ambiguous variable {key}: {candidates}')
        da = ds[candidates[0]]
        if set(da.dims) != set(COORDS):
            raise ValueError(f'{key} must have exactly time, depth, latitude, longitude dimensions.')
        units = da.attrs.get('units', '').lower().replace(' ', '')
        standard = da.attrs.get('standard_name')
        if standard and standard != meta['standard']:
            raise ValueError(f'{key}: {standard} is not the supported {meta["standard"]}. Convert upstream.')
        if meta.get('plugin'):
            if units not in meta['unit_aliases'] or standard != meta['standard']:
                raise ValueError(f'{key}: require canonical units and standard_name declared by its plugin.')
            if meta['standard'] is None and not da.attrs.get('long_name'):
                raise ValueError(f'{key}: a source-specific quantity needs an explicit long_name; do not invent a CF standard_name.')
        elif key == 'temperature':
            if units in ('k', 'kelvin'):
                da = da - 273.15
            elif units not in ('degc', 'degree_celsius', 'degrees_celsius', 'celsius', '°c'):
                raise ValueError('Temperature units must be Celsius or Kelvin.')
            if not standard:
                raise ValueError('Temperature must declare standard_name=sea_water_potential_temperature to avoid mixing temperature definitions.')
        elif key in ('analyzed_temperature', 'temperature_spread'):
            if units not in ('degc', 'degree_celsius', 'degrees_celsius', 'celsius', '°c'):
                raise ValueError('Analyzed temperature and spread require explicit Celsius units.')
            if not da.attrs.get('long_name'):
                raise ValueError('Source-specific quantities require a descriptive long_name.')
        elif key in ('u', 'v'):
            if units in ('cm/s', 'cms-1'):
                da = da / 100
            elif units not in ('m/s', 'ms-1', 'm.s-1'):
                raise ValueError('Current units must be m/s or cm/s.')
        elif key == 'chlorophyll':
            if units in ('kgm-3', 'kg/m3'):
                da = da * 1e6
            elif units not in ('mgm-3', 'mg/m3', 'mg/m³'):
                raise ValueError('Chlorophyll units must be mg/m3 or kg/m3.')
        elif units not in ('1', 'psu', '1e-3', '0.001'):
            raise ValueError('Salinity must be practical salinity (1, PSU, or 1e-3).')
        found[key] = da.transpose('time', 'depth', 'latitude', 'longitude').astype('float32')
        found[key].attrs = dict(units=meta['unit'], long_name=meta['label'])
        if meta['standard']: found[key].attrs['standard_name']=meta['standard']
    if not found:
        raise ValueError('No supported ocean variables found.')
    return xr.Dataset(found, coords={k: ds[k] for k in COORDS}, attrs=ds.attrs)


def open_bounded_model(path):
    """Bound Dask tasks even when a source is a contiguous, unchunked NetCDF."""
    raw = xr.open_dataset(path)
    return bound_model(raw)


def bound_model(raw):
    """Shared normalization for built-in and administrator model adapters; owns raw."""
    try:
        for variable in raw.data_vars.values():
            chunks = variable.encoding.get('chunksizes')
            if chunks and np.prod(chunks) * variable.dtype.itemsize > 32 * 1024 * 1024:
                raise ValueError('A source storage chunk exceeds 32 MiB; rechunk the file upstream.')
        chunks = {dim: (1 if dim in raw.coords and np.issubdtype(raw[dim].dtype, np.datetime64) else min(64, size)) for dim,size in raw.sizes.items()}
        return raw, normalize(raw.chunk(chunks))
    except Exception:
        raw.close()
        raise

@dataclass
class Model:
    id: str
    ds: xr.Dataset
    provenance: dict
    source: xr.Dataset | None = None

    def close(self):
        self.ds.close()
        if self.source is not None:
            self.source.close()

    def catalog(self):
        return dict(id=self.id, title=self.provenance['title'], provenance=self.provenance,
                    variables=[dict(id=k, **VARIABLES[k]) for k in self.ds.data_vars],
                    times=[np.datetime_as_string(t, unit='s') + 'Z' for t in self.ds.time.values],
                    bounds=[float(self.ds.longitude.min()), float(self.ds.latitude.min()), float(self.ds.longitude.max()), float(self.ds.latitude.max())],
                    depths=clean(self.ds.depth.values), shape=dict(self.ds.sizes))

    def sample(self, variable, lon, lat, depth, time, max_gap_hours=48):
        """4D linear interpolation with contributing-corner masks and bounded time gaps."""
        if variable not in self.ds:
            raise ValueError(f'Variable {variable} unavailable.')
        arrays = np.broadcast_arrays(lon, lat, depth, np.asarray(time, dtype='datetime64[ns]'))
        lon, lat, depth, dates = [a.ravel() for a in arrays]
        if not len(lon):
            return np.empty(0)
        if np.isnat(dates).any() or not all(np.isfinite(a).all() for a in (lon, lat, depth)):
            raise ValueError('Sampling coordinates and times must be finite.')
        ts = self.ds.time.values.astype('datetime64[ns]').astype('int64') / 1e9
        query_t = dates.astype('int64') / 1e9
        # Subset before loading, retaining one bracketing cell on each side.
        selectors = {}
        for name, query in [('time', query_t), ('depth', depth), ('latitude', lat), ('longitude', lon)]:
            coord = ts if name == 'time' else self.ds[name].values
            lo = max(0, int(np.searchsorted(coord, np.min(query))) - 1)
            hi = min(len(coord), int(np.searchsorted(coord, np.max(query), side='right')) + 1)
            if hi - lo < 2:
                lo, hi = max(0, min(lo, len(coord)-2)), min(len(coord), max(hi, 2))
            selectors[name] = slice(lo, hi)
        region = self.ds[variable].isel(**selectors)
        if region.size > 8_000_000:
            raise ValueError('Analysis subset too large; narrow the region or time window.')
        axes = (ts[selectors['time']], region.depth.values, region.latitude.values, region.longitude.values)
        values = multilinear(axes, region.values, np.column_stack([query_t, depth, lat, lon]))
        if len(ts) == 1:
            return values
        right = np.clip(np.searchsorted(ts, query_t), 1, len(ts)-1)
        gap = (ts[right] - ts[right-1]) / 3600
        exact = np.isin(query_t, ts)
        values[(gap > max_gap_hours) & ~exact] = np.nan
        return values

    def volume(self, variable, index, resolution=36, maximum_depth=None, bbox=None):
        if variable not in self.ds or index < 0 or index >= self.ds.sizes['time']:
            raise ValueError('Variable or time index unavailable.')
        if not isinstance(resolution, int) or not 8 <= resolution <= 64:
            raise ValueError('Display resolution must be 8–64.')
        bounds = [float(self.ds.longitude.min()), float(self.ds.latitude.min()), float(self.ds.longitude.max()), float(self.ds.latitude.max())]
        if bbox is not None:
            if len(bbox) != 4 or not np.isfinite(bbox).all() or bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                raise ValueError('Display region requires finite west,south,east,north with positive extent.')
            if bbox[0] < bounds[0] or bbox[1] < bounds[1] or bbox[2] > bounds[2] or bbox[3] > bounds[3]:
                raise ValueError('Display region must remain inside the model bounds.')
            bounds = list(bbox)
        # Uniform output grid is necessary for vtkImageData. Original data stays unchanged.
        axes = {k: np.linspace(float(self.ds[k].min()), float(self.ds[k].max()), min(resolution, self.ds.sizes[k])) for k in ('longitude', 'latitude', 'depth')}
        axes['longitude'] = np.linspace(bounds[0], bounds[2], len(axes['longitude']))
        axes['latitude'] = np.linspace(bounds[1], bounds[3], len(axes['latitude']))
        if self.provenance.get('display_upsampling'):
            axes['longitude'] = np.linspace(bounds[0], bounds[2], resolution)
            axes['latitude'] = np.linspace(bounds[1], bounds[3], resolution)
        if maximum_depth is not None:
            if not np.isfinite(maximum_depth) or maximum_depth <= 0:
                raise ValueError('Display maximum depth must be finite and positive.')
            end = min(float(self.ds.depth.max()), float(maximum_depth))
            if not np.isfinite(end) or end <= float(self.ds.depth.min()):
                raise ValueError('Display depth window contains no vertical interval.')
            # A denser display grid resolves the selected interval; it never adds source information.
            axes['depth'] = np.linspace(float(self.ds.depth.min()), end, min(96, resolution*2))
        da = self.ds[variable].isel(time=index)
        # Gather the actual bracketing source cells. Decimation before interpolation
        # can bridge a narrow masked coastline or erase a feature, so never do it.
        selectors = {}
        for k, target in axes.items():
            right = np.clip(np.searchsorted(da[k].values, target, side='right'), 1, da.sizes[k]-1)
            selectors[k] = np.unique(np.concatenate([right-1, right]))
        reduced = da.isel(**selectors).transpose('depth', 'latitude', 'longitude')
        z, y, x = np.meshgrid(axes['depth'], axes['latitude'], axes['longitude'], indexing='ij')
        render = multilinear([reduced[k].values for k in ('depth','latitude','longitude')], reduced.values,
                             np.column_stack([z.ravel(),y.ravel(),x.ravel()])).reshape(z.shape)
        vals = render[np.isfinite(render)]
        return dict(model_id=self.id, variable=variable, time=np.datetime_as_string(self.ds.time.values[index], unit='s')+'Z',
                    dimensions=[len(axes[k]) for k in ('longitude', 'latitude', 'depth')],
                    axes={k:v.tolist() for k,v in axes.items()}, values=clean(render.ravel()),
                    range=clean([vals.min(), vals.max()]) if len(vals) else None,
                    valid_cells=int(len(vals)), total_cells=int(render.size),
                    order='x-fastest, then latitude, then positive-down depth',
                    maximum_depth=maximum_depth,
                    bbox=bounds,
                    sampling=dict(selected_source_cells=int(reduced.size), source_frame_cells=int(da.size),
                                  resolution=resolution, native_shape=dict(da.sizes)),
                    method='trilinear resampling from original bracketing cells; positive-weight missing corners invalidate; no source decimation; display sampling does not increase native resolution', provenance=self.provenance)

def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()
