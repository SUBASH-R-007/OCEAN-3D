"""Documented long/wide observation tables; no guessed physical definitions."""
import csv
import io
import shlex
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from .science import VARIABLES

MISSING = {'', 'na', 'n/a', 'nan', 'null'}
HEADERS = {'lon': 'longitude', 'lat': 'latitude', 'timestamp': 'time',
           'date_time': 'time', 'depth_m': 'depth', 'units': 'unit'}


def variable_id(name):
    name = name.strip().lower()
    matches = [k for k, v in VARIABLES.items() if name in [k, *v['aliases'], v['standard']]]
    if len(matches) != 1:
        raise ValueError(f'Unknown or ambiguous observation variable: {name}. Register its definition before import.')
    return matches[0]


def unit_transform(key, unit):
    """Return affine conversion to the registered physical definition."""
    u = unit.lower().replace(' ', '')
    if VARIABLES[key].get('plugin'):
        if u in VARIABLES[key]['unit_aliases']: return 1., 0.
    elif key in ('temperature', 'analyzed_temperature', 'temperature_spread'):
        if u in ('°c', 'degc', 'celsius', 'degree_celsius', 'degrees_celsius'): return 1., 0.
        if u in ('k', 'kelvin'): return 1., (0. if key == 'temperature_spread' else -273.15)
    elif key == 'salinity':
        if u in ('psu', '1', '1e-3', '0.001'): return 1., 0.
    elif key in ('u', 'v'):
        if u in ('m/s', 'ms-1', 'm.s-1'): return 1., 0.
        if u in ('cm/s', 'cms-1'): return .01, 0.
    elif key == 'chlorophyll':
        if u in ('mg/m³', 'mg/m3', 'mgm-3', 'mg/m^3'): return 1., 0.
        if u in ('kg/m3', 'kgm-3'): return 1e6, 0.
    raise ValueError(f'{key}: unsupported unit {unit!r}; expected {VARIABLES[key]["unit"]} or a documented convertible unit.')


def number(value, name, optional=False):
    if value.lower() in MISSING and optional: return None
    try: result = float(value)
    except ValueError as exc: raise ValueError(f'{name} must be numeric.') from exc
    if not np.isfinite(result):
        if optional and value.lower() in MISSING: return None
        raise ValueError(f'{name} must be finite.')
    return result


def boolean(value, name):
    if value.lower() not in ('true', 'false', ''): raise ValueError(f'{name} must be true or false.')
    return value.lower() == 'true'


def parse_delimited(path: Path):
    from .observations import validate_profile
    raw = path.read_text(encoding='utf-8-sig')
    if '\x00' in raw: raise ValueError('Observation tables must be UTF-8 text, not binary files.')
    # Comment preambles are allowed before the header, never stripped inside quoted fields.
    lines = raw.splitlines(keepends=True)
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith('#')): lines.pop(0)
    if not lines: raise ValueError('The observation file is empty.')
    header = lines[0]
    delimiters = [d for d in (',', '\t', ';', '|') if d in header]
    if len(delimiters) > 1: raise ValueError('Ambiguous header delimiter; use one of comma, tab, semicolon or pipe.')
    delimiter = delimiters[0] if delimiters else None
    if delimiter:
        reader = csv.reader(io.StringIO(''.join(lines)), delimiter=delimiter, strict=True)
    else:
        reader = (shlex.split(line, comments=False) for line in lines if line.strip())
    try: names = [HEADERS.get(n.strip().lower(), n.strip().lower()) for n in next(reader)]
    except (StopIteration, csv.Error) as exc: raise ValueError('No readable table header.') from exc
    if len(names) != len(set(names)) or any(not n for n in names): raise ValueError('Table headers must be nonempty and unique after alias mapping.')
    required = {'profile_id', 'instrument', 'longitude', 'latitude', 'time', 'depth'}
    if not required.issubset(names): raise ValueError('Delimited file requires columns: '+', '.join(sorted(required)))
    long = 'variable' in names or 'value' in names
    if long and not {'variable', 'value'}.issubset(names): raise ValueError('Long tables require both variable and value columns.')
    common = required | {'variable','value','qc','unit','adjusted','error','data_mode','synthetic','depth_unit','standard_name'}
    channels = []
    if not long:
        for name in names:
            if name in common or name.endswith(('_qc','_unit','_error','_adjusted','_standard_name')): continue
            channels.append((name, variable_id(name)))
        if not channels: raise ValueError('Wide table requires at least one registered variable column.')
        if len({key for _,key in channels}) != len(channels): raise ValueError('Wide table has multiple columns for the same variable.')
        valid = common | {name for name,_ in channels} | {name+suffix for name,_ in channels for suffix in ('_qc','_unit','_error','_adjusted','_standard_name')}
    else: valid = common
    unknown = set(names) - valid
    if unknown: raise ValueError('Unrecognized columns: '+', '.join(sorted(unknown))+'. Map them to the documented schema first.')
    profiles = {}; total = 0
    try:
        i = 1
        for cells in reader:
            if not cells: continue
            i += 1
            try:
                if len(cells) != len(names): raise ValueError(f'Expected {len(names)} fields, found {len(cells)}.')
                row = dict(zip(names, (c.strip() for c in cells)))
                pid = row['profile_id']
                if not pid or len(pid) > 160 or not row['instrument']: raise ValueError('Nonempty profile_id (at most 160 characters) and instrument required.')
                lon, lat = number(row['longitude'],'longitude'), number(row['latitude'],'latitude')
                if not -180 <= lon <= 180 or not -90 <= lat <= 90: raise ValueError('Invalid observation coordinates.')
                date = datetime.fromisoformat(row['time'].replace('Z','+00:00'))
                if date.tzinfo is None: raise ValueError('Observation time requires an explicit UTC offset.')
                date = date.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
                depth_unit = row.get('depth_unit') or 'm'
                if depth_unit not in ('m','km'): raise ValueError('depth_unit must be m or km, positive down; pressure requires a dedicated adapter.')
                depth = number(row['depth'],'depth') * (1000 if depth_unit == 'km' else 1)
                if depth < 0: raise ValueError('Depth must be positive down.')
                synthetic = boolean(row.get('synthetic','false'),'synthetic')
                mode = row.get('data_mode') or 'unknown'
                p = profiles.setdefault(pid, dict(id=pid, instrument=row['instrument'], longitude=lon, latitude=lat, time=date, data_mode=mode, source='User import: '+path.name, synthetic=synthetic, samples=[], path=[], import_warnings=[]))
                if (p['instrument'],p['synthetic'],p['data_mode']) != (row['instrument'],synthetic,mode): raise ValueError('Instrument, synthetic flag and data mode must agree within each profile_id.')
                selected = [(None,variable_id(row['variable']))] if long else channels
                for column,key in selected:
                    def field(name, default=''):
                        return row.get((column+'_'+name) if column else name, row.get(name,default)) or default
                    unit = field('unit')
                    if not unit:
                        if VARIABLES[key].get('plugin'): raise ValueError('Plugin observation variables require an explicit canonical unit column.')
                        unit = VARIABLES[key]['unit']
                        warning = f'{key}: no unit supplied; documented canonical {unit} assumed.'
                        if warning not in p['import_warnings']: p['import_warnings'].append(warning)
                    standard = field('standard_name')
                    if standard and standard != VARIABLES[key]['standard']: raise ValueError(f'{key}: incompatible standard_name {standard}; temperature means potential temperature, not in-situ temperature.')
                    scale, offset = unit_transform(key,unit)
                    value = number(row[column] if column else row['value'],key,optional=True)
                    error = number(field('error'),key+' error',optional=True)
                    if error is not None and error < 0: raise ValueError('Instrument error must be nonnegative.')
                    quality = number(field('qc','0'),key+' QC')
                    if quality != int(quality) or not 0 <= quality <= 9: raise ValueError('Quality flag must be an integer 0–9.')
                    if not field('qc') and 'Missing QC stays unknown (0); no good-data flag is inferred.' not in p['import_warnings']: p['import_warnings'].append('Missing QC stays unknown (0); no good-data flag is inferred.')
                    p['samples'].append(dict(depth=depth,variable=key,value=value*scale+offset if value is not None else None,qc=int(quality),adjusted=boolean(field('adjusted','false'),'adjusted'),error=error*abs(scale) if error is not None else None,longitude=lon,latitude=lat,time=date,source_value=value,source_unit=unit,source_depth=number(row['depth'],'depth'),source_depth_unit=depth_unit,source_qc=int(quality),source_row=i))
                    total += 1
                    if total > 200_000: raise ValueError('Maximum 200,000 observation values per import.')
                point = dict(longitude=lon,latitude=lat,depth=depth,time=date)
                if not p['path'] or point != p['path'][-1]: p['path'].append(point)
                if len(profiles) > 10_000: raise ValueError('Maximum 10,000 profiles per import.')
            except (ValueError, OverflowError) as exc: raise ValueError(f'Table record {i}: {exc}') from exc
    except csv.Error as exc: raise ValueError(f'Malformed quoted table: {exc}') from exc
    if not profiles: raise ValueError('No observation rows found.')
    for p in profiles.values():
        points = sorted(p['path'],key=lambda x:x['time'])
        p['time_range']=[points[0]['time'],points[-1]['time']]
        p.update({k:points[0][k] for k in ('longitude','latitude','time')})
        if len({(x['longitude'],x['latitude'],x['time']) for x in points}) > 1:
            p['path']=points
            p['warning']='Sample positions and times are retained; path segments connect supplied readings, not an inferred vehicle route.'
        else: p.pop('path')
        p['table_layout']='long' if long else 'wide'
        p['delimiter']={'\t':'tab',',':'comma',';':'semicolon','|':'pipe',None:'whitespace'}[delimiter]
    return [validate_profile(p) for p in profiles.values()]
