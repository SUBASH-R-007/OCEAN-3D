"""Bounded adapters for documented IMOS glider and CCHDO CTD products."""
from pathlib import Path
import json
import numpy as np
import xarray as xr
import gsw


def timestamp(value):
    if np.isnat(value):
        raise ValueError('Instrument timestamps must be finite.')
    return np.datetime_as_string(value, unit='us') + 'Z'


def number(value):
    return float(value) if np.isfinite(value) else None


def combined(*flags):
    return 0 if 0 in flags else max(flags)


def source_flags(ds, name, mapping):
    da = ds[name]
    names = str(da.attrs.get('ancillary_variables', '')).split()
    candidates = [ds[n] for n in names if n in ds and 'flag_meanings' in ds[n].attrs]
    if len(candidates) != 1:
        raise ValueError(f'{name} requires one explicit quality flag variable.')
    flag = candidates[0]
    meanings = str(flag.attrs['flag_meanings']).split()
    values = np.asarray(flag.attrs.get('flag_values', [])).ravel()
    if len(values) != len(meanings) or flag.dims != da.dims:
        raise ValueError(f'{name} quality metadata does not match its values.')
    lookup = {float(v): mapping.get(m, 0) for v, m in zip(values, meanings)}
    native = flag.values
    canonical = np.array([lookup.get(float(v), 0) for v in native.ravel()], dtype='int8').reshape(native.shape)
    return canonical, native


IMOS_QC = {'good_data': 1, 'probably_good_data': 2, 'bad_data_that_are_potentially_correctable': 3, 'bad_data': 4, 'missing_values': 9}
WOCE_QC = {'acceptable_measurement': 1, 'questionable_measurement': 3, 'bad_measurement': 4, 'not_reported': 9, 'not_sampled': 9}


def parse_imos_glider(path: Path):
    from .observations import validate_profile
    with xr.open_dataset(path) as source:
        if not 0 < source.sizes.get('TIME', 0) <= 200_000:
            raise ValueError('IMOS glider imports require a subset of at most 200,000 native samples.')
        ds = source.load()
    expected = {'TIME': ('time', None), 'LATITUDE': ('latitude', 'degrees_north'), 'LONGITUDE': ('longitude', 'degrees_east'), 'DEPTH': ('depth', 'm'), 'PRES': ('sea_water_pressure', 'dbar'), 'TEMP': ('sea_water_temperature', 'Celsius'), 'PSAL': ('sea_water_salinity', '1e-3')}
    for name, (standard, unit) in expected.items():
        if name not in ds or ds[name].dims != ('TIME',) or ds[name].attrs.get('standard_name') != standard or (unit and ds[name].attrs.get('units') != unit):
            raise ValueError(f'Unexpected IMOS {name} definition, dimensions or units.')
    if ds.DEPTH.attrs.get('positive') != 'down' or any(n not in ds for n in ['PROFILE', 'PHASE']):
        raise ValueError('IMOS profiles need native profile/phase identifiers and positive-down depth.')
    if not np.issubdtype(ds.TIME.dtype, np.datetime64):
        raise ValueError('IMOS time must decode to Gregorian timestamps.')
    channels = [('temperature', 'TEMP'), ('salinity', 'PSAL')]
    if 'CPHL' in ds:
        if ds.CPHL.attrs.get('units') != 'mg m-3' or ds.CPHL.attrs.get('standard_name') != 'mass_concentration_of_chlorophyll_in_sea_water':
            raise ValueError('IMOS chlorophyll units/definition differ.')
        channels.append(('chlorophyll', 'CPHL'))
    flags = {name: source_flags(ds, name, IMOS_QC) for name in ['TEMP', 'PSAL', 'PRES', 'DEPTH', 'TIME', *(['CPHL'] if 'CPHL' in ds else [])]}
    for n in ['LATITUDE_quality_control', 'LONGITUDE_quality_control']:
        if n not in ds: raise ValueError('IMOS underwater positions require their source quality flags.')
    lon, lat, depth, time = [ds[n].values for n in ['LONGITUDE','LATITUDE','DEPTH','TIME']]
    position = np.isfinite(lon) & np.isfinite(lat) & (abs(lon) <= 180) & (abs(lat) <= 90)
    # IMOS flags 8 are explicitly interpolated underwater positions, not GPS fixes.
    position &= np.isin(ds.LATITUDE_quality_control.values,[1,2,8]) & np.isin(ds.LONGITUDE_quality_control.values,[1,2,8])
    finite = position & np.isfinite(depth) & (depth >= 0) & ~np.isnat(time) & np.isin(flags['TIME'][0],[1,2])
    absolute = gsw.SA_from_SP(np.where(ds.PSAL.values >= 0, ds.PSAL.values, np.nan), ds.PRES.values, lon, lat)
    potential = gsw.pt0_from_t(absolute, ds.TEMP.values, ds.PRES.values)
    out=[]
    for identity in np.unique(ds.PROFILE.values[np.isfinite(ds.PROFILE.values) & (ds.PROFILE.values > 0)]):
        indices = np.flatnonzero((ds.PROFILE.values == identity) & finite)
        if len(indices) < 2: continue
        phases = np.unique(ds.PHASE.values[indices])
        if len(phases) != 1 or phases[0] not in (1,4): continue
        direction = 'descent' if phases[0] == 1 else 'ascent'
        rows=[]
        for j in indices:
            for variable,name in channels:
                inputs=[int(flags[name][0][j]),int(flags['DEPTH'][0][j])]
                if variable=='temperature': inputs.extend([int(flags['PSAL'][0][j]),int(flags['PRES'][0][j])])
                rows.append(dict(depth=float(depth[j]),variable=variable,value=number(potential[j] if variable=='temperature' else ds[name].values[j]),qc=combined(*inputs),source_qc=number(flags[name][1][j]),adjusted=False,error=None,longitude=float(lon[j]),latitude=float(lat[j]),time=timestamp(time[j]),source_index=int(j),source_in_situ_temperature=number(ds.TEMP.values[j]) if variable=='temperature' else None,position_qc=[int(ds.LONGITUDE_quality_control.values[j]),int(ds.LATITUDE_quality_control.values[j])]))
        trajectory=[dict(longitude=float(lon[j]),latitude=float(lat[j]),depth=float(depth[j]),time=timestamp(time[j]),break_before=bool(k and j!=indices[k-1]+1)) for k,j in enumerate(indices)]
        first=int(indices[0])
        out.append(validate_profile(dict(id=f'IMOS-{ds.attrs.get("platform_code","glider")}-{int(identity)}',instrument='Glider',longitude=float(lon[first]),latitude=float(lat[first]),time=timestamp(time[first]),time_range=[timestamp(time[indices[0]]),timestamp(time[indices[-1]])],data_mode='IMOS FV01 quality-controlled',source=ds.attrs.get('title',path.name),synthetic=False,samples=rows,path=trajectory,trajectory_id=str(ds.attrs.get('title',path.stem)),feature_type='trajectoryprofile',phase=direction,warning='Native underwater positions are interpolated between navigation fixes (IMOS position flag 8). Each sample retains its position, time and source QC; a marker denotes the first accepted position of the cast.',conversion='GSW: native practical salinity, pressure and position to potential temperature at 0 dbar. Native depths and in-situ temperatures retained. Temperature QC combines temperature, salinity, pressure and depth flags.',license=ds.attrs.get('license'),acknowledgement=ds.attrs.get('acknowledgement'))))
    if not out: raise ValueError('No valid native IMOS descent/ascent profiles.')
    return out


def parse_cchdo_ctd(path: Path):
    from .observations import validate_profile, text
    with xr.open_dataset(path) as source:
        if source.sizes.get('N_PROF',0)*source.sizes.get('N_LEVELS',0) > 200_000:
            raise ValueError('CCHDO CTD imports require a subset of at most 200,000 levels.')
        ds=source.load()
    expected={'pressure':('sea_water_pressure','dbar'),'ctd_temperature':('sea_water_temperature','degC'),'ctd_salinity':('sea_water_practical_salinity','1')}
    for name,(standard,unit) in expected.items():
        if name not in ds or ds[name].dims!=('N_PROF','N_LEVELS') or ds[name].attrs.get('standard_name')!=standard or ds[name].attrs.get('units')!=unit:
            raise ValueError(f'Unexpected CCHDO {name} definition or units.')
    for name,standard,unit in [('longitude','longitude','degree_east'),('latitude','latitude','degree_north')]:
        if ds[name].dims!=('N_PROF',) or ds[name].attrs.get('standard_name')!=standard or ds[name].attrs.get('units')!=unit: raise ValueError('CCHDO geographic coordinate metadata differs.')
    if ds.time.dims!=('N_PROF',) or not np.issubdtype(ds.time.dtype,np.datetime64): raise ValueError('CCHDO timestamps must decode to Gregorian times.')
    tq,tn=source_flags(ds,'ctd_temperature',WOCE_QC);sq,sn=source_flags(ds,'ctd_salinity',WOCE_QC)
    out=[]
    for i in range(ds.sizes['N_PROF']):
        lon,lat=float(ds.longitude[i]),float(ds.latitude[i]);date=timestamp(ds.time.values[i])
        pressure=ds.pressure.values[i];salt=ds.ctd_salinity.values[i];temp=ds.ctd_temperature.values[i]
        depth=-gsw.z_from_p(pressure,lat);potential=gsw.pt0_from_t(gsw.SA_from_SP(np.where(salt>=0,salt,np.nan),pressure,lon,lat),temp,pressure)
        rows=[]
        for j in np.flatnonzero(np.isfinite(depth)&(depth>=0)):
            for variable,value,flag,native in [('temperature',potential[j],combined(int(tq[i,j]),int(sq[i,j])),tn[i,j]),('salinity',salt[j],int(sq[i,j]),sn[i,j])]:
                rows.append(dict(depth=float(depth[j]),variable=variable,value=number(value),qc=flag,source_qc=number(native),adjusted=False,error=None,source_index=int(j),source_pressure_dbar=float(pressure[j]),source_in_situ_temperature=number(temp[j]) if variable=='temperature' else None))
        if not rows:continue
        cruise=text(ds.expocode.values[i]);station=text(ds.station.values[i]);cast=text(ds.cast.values[i])
        out.append(validate_profile(dict(id=f'CCHDO-{cruise}-{station}-{cast}',instrument='CTD',longitude=lon,latitude=lat,time=date,data_mode='CCHDO CTD processed',source=f'GO-SHIP {text(ds.section_id.values[i])} · {cruise} · station {station}, cast {cast}',synthetic=False,samples=rows,feature_type='profile',warning='WOCE flag 2 (acceptable measurement) maps to canonical QC 1. Uncalibrated, interpolated and despiked flags are not promoted to good. No pressure quality flag or instrument uncertainty is supplied.',conversion='GSW: measured pressure to depth at cast latitude; practical salinity and in-situ ITS-90 temperature to potential temperature at 0 dbar. Source pressure, in-situ temperature and WOCE flags retained.')))
    if not out:raise ValueError('No valid CCHDO CTD casts.')
    return out


def load_instrument_cases(folder=None, force_parse=False):
    from .observations import ADAPTERS, validate_profile
    from .science import file_hash
    folder=Path(folder) if folder else Path(__file__).resolve().parents[1]/'data/instruments'
    if not (folder/'manifest.json').is_file():return []
    info=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    profiles=[]
    for item in info['sources']:
        path=folder/item['file']
        if path.resolve().parent!=folder.resolve() or file_hash(path)!=item['sha256']:raise ValueError('Instrument source path or checksum differs from its manifest.')
        original=folder/item.get('original_source_file',item['file'])
        if original.resolve().parent!=folder.resolve() or file_hash(original)!=item.get('original_source_sha256',item['sha256']):raise ValueError('Original instrument source checksum differs from its manifest.')
    if info.get('normalized') and not force_parse:
        cached=folder/info['normalized']['file']
        if cached.resolve().parent!=folder.resolve() or file_hash(cached)!=info['normalized']['sha256']:raise ValueError('Normalized instrument cache checksum differs from its manifest.')
        profiles=[validate_profile(p) for p in json.loads(cached.read_text(encoding='utf-8'))]
        if len({p['id'] for p in profiles})!=len(profiles):raise ValueError('Instrument cache contains duplicate identities.')
        return profiles
    for item in info['sources']:
        path=folder/item['file']
        for p in ADAPTERS[item['adapter']](path):
            p.update({k:v for k,v in item.items() if k in ['source_url','source_download_url','sha256','license','acknowledgement','original_source_sha256']})
            profiles.append(p)
    if len({p['id'] for p in profiles})!=len(profiles):raise ValueError('Instrument cases contain duplicate profile identities.')
    return profiles
