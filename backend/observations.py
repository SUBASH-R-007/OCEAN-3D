"""Adapters for a documented delimited schema and Argo GDAC profile NetCDF."""
from pathlib import Path
import numpy as np
import xarray as xr
import gsw
from datetime import datetime, timezone

def text(v):
    a = np.asarray(v).ravel()
    return ''.join(x.decode() if isinstance(x, bytes) else str(x) for x in a).strip()

def validate_profile(p):
    if not (-90 <= p['latitude'] <= 90 and -180 <= p['longitude'] <= 180):
        raise ValueError('Invalid observation coordinates.')
    try:
        date = datetime.fromisoformat(p['time'].replace('Z', '+00:00'))
        if date.tzinfo is None:
            raise ValueError('Timezone required')
        p['time'] = date.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    except ValueError as exc:
        raise ValueError('Observation timestamp must be ISO 8601 with an explicit UTC offset.') from exc
    for row in p['samples']:
        if not np.isfinite(row['depth']) or row['depth'] < 0:
            raise ValueError('Observation depth must be finite and positive down.')
        if row['qc'] not in range(10):
            raise ValueError('Quality flag must be 0-9.')
        if row['error'] is not None and (not np.isfinite(row['error']) or row['error'] < 0):
            raise ValueError('Instrument error must be finite and nonnegative when supplied.')
        for name,limit in (('longitude',180),('latitude',90)):
            if name in row and not -limit <= row[name] <= limit:
                raise ValueError('Invalid sample coordinates.')
        if 'time' in row:
            date=datetime.fromisoformat(row['time'].replace('Z','+00:00'))
            if date.tzinfo is None: raise ValueError('Sample timestamp requires an explicit UTC offset.')
            row['time']=date.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
    p['samples'].sort(key=lambda r:r['depth'])
    if p['samples']:
        p['depth_range']=[p['samples'][0]['depth'],p['samples'][-1]['depth']]
    return p

def parse_csv(path: Path):
    from .delimited import parse_delimited
    return parse_delimited(path)

def parse_argo(path: Path):
    with xr.open_dataset(path) as ds:
        if 'N_PROF' not in ds.dims or not {'PRES','TEMP','PSAL','LONGITUDE','LATITUDE','JULD'}.issubset(ds.variables):
            raise ValueError('Expected Argo GDAC profile NetCDF with N_PROF, PRES, TEMP, PSAL, position and JULD.')
        if ds.sizes['N_PROF'] * ds.sizes.get('N_LEVELS', 1) > 200_000:
            raise ValueError('Argo import exceeds 200,000 levels.')
        out = []
        for i in range(ds.sizes['N_PROF']):
            d = ds.isel(N_PROF=i)
            if ('POSITION_QC' in d and text(d.POSITION_QC.values) != '1') or ('JULD_QC' in d and text(d.JULD_QC.values) != '1'):
                continue
            lon,lat = float(d.LONGITUDE),float(d.LATITUDE)
            if not np.isfinite([lon,lat]).all() or np.isnat(d.JULD.values):
                continue
            date = np.datetime_as_string(d.JULD.values, unit='us')+'Z'
            mode = text(d.DATA_MODE.values) if 'DATA_MODE' in d else 'R'
            parameter_modes = {}
            if 'PARAMETER_DATA_MODE' in d and 'STATION_PARAMETERS' in d:
                for name, flag in zip(d.STATION_PARAMETERS.values, d.PARAMETER_DATA_MODE.values):
                    parameter_modes[text(name)] = text(flag)
            def values(name):
                adj = name+'_ADJUSTED'
                # D/A means adjusted only, even when every adjusted level is absent.
                # BGC parameters may have different processing modes in one profile.
                use = adj if parameter_modes.get(name, mode) in ('A','D') else name
                val = np.asarray(d[use].values).ravel() if use in d else np.full(d.sizes['N_LEVELS'], np.nan)
                qc = [int(text(x)) if text(x).isdigit() else 0 for x in d[use+'_QC'].values.ravel()] if use+'_QC' in d else [0]*len(val)
                err = d[use+'_ERROR'].values.ravel() if use+'_ERROR' in d else np.full(len(val),np.nan)
                return val,np.asarray(qc),err,use==adj
            pres,pqc,pe,pa = values('PRES')
            temp,tqc,te,ta = values('TEMP')
            sal,sqc,se,sa = values('PSAL')
            depths = -gsw.z_from_p(pres,lat)
            sal = np.where(sal >= 0, sal, np.nan)
            absolute = gsw.SA_from_SP(sal,pres,lon,lat)
            potential = gsw.pt0_from_t(absolute,temp,pres)
            rows=[]
            for j in range(len(pres)):
                if not np.isfinite(depths[j]) or depths[j]<0:
                    continue
                for name, vals, flags, errors, adjusted in [('temperature',potential,np.maximum.reduce([tqc,sqc,pqc]),te,ta and sa and pa),('salinity',sal,np.maximum(sqc,pqc),se,sa and pa)]:
                    # Every input to TEOS conversion must pass; unknown QC must remain unknown.
                    input_flags = [pqc[j],sqc[j]] + ([tqc[j]] if name=='temperature' else [])
                    flag = 0 if 0 in input_flags else int(flags[j])
                    rows.append(dict(depth=round(float(depths[j]),3),variable=name,value=float(vals[j]) if np.isfinite(vals[j]) else None,qc=flag,adjusted=bool(adjusted),error=float(errors[j]) if np.isfinite(errors[j]) else None,pressure_error_dbar=float(pe[j]) if np.isfinite(pe[j]) else None))
            if 'CHLA' in d:
                units=d.CHLA.attrs.get('units','').lower().replace(' ','')
                if units not in ('mg/m3','mgm-3','mg/m^3','mg/m³'):
                    raise ValueError('Argo CHLA must explicitly use mg/m3; convert unsupported units upstream.')
                chl,cqc,ce,ca=values('CHLA')
                for j in range(len(pres)):
                    if not np.isfinite(depths[j]) or depths[j]<0: continue
                    flags=[pqc[j],cqc[j]]
                    rows.append(dict(depth=round(float(depths[j]),3),variable='chlorophyll',value=float(chl[j]) if np.isfinite(chl[j]) else None,
                                     qc=0 if 0 in flags else int(max(flags)),adjusted=bool(pa and ca),error=float(ce[j]) if np.isfinite(ce[j]) else None,
                                     pressure_error_dbar=float(pe[j]) if np.isfinite(pe[j]) else None))
            pid = text(d.PLATFORM_NUMBER.values) if 'PLATFORM_NUMBER' in d else path.stem
            cycle = int(d.CYCLE_NUMBER) if 'CYCLE_NUMBER' in d else i
            out.append(validate_profile(dict(id=f'{pid}-{cycle}-{i}',instrument='BGC Argo' if 'CHLA' in d else 'Argo',longitude=lon,latitude=lat,time=date,data_mode=mode,parameter_data_modes=parameter_modes,source='Argo GDAC: '+path.name,synthetic=False,samples=rows,conversion='GSW: PRES→depth using latitude; SP→SA; in-situ TEMP→potential temperature at 0 dbar. Errors are source instrument errors, not propagated potential-temperature or total comparison uncertainty.')))
        if not out:
            raise ValueError('No valid-position, valid-time Argo profiles found.')
        return out

from .cf_profiles import parse_cf_profiles
from .instrument_sources import parse_imos_glider, parse_cchdo_ctd

ADAPTERS = {'csv':parse_csv,'tsv':parse_csv,'txt':parse_csv,'argo':parse_argo,'cf-profile':parse_cf_profiles,'imos-glider':parse_imos_glider,'cchdo-ctd':parse_cchdo_ctd}
