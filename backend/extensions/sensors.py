"""Explicit canonical table contracts, not raw vendor/radial/beam decoders."""
from collections import defaultdict
from copy import deepcopy
from ..delimited import parse_delimited
from ..plugins import register_observation_adapter, register_sensor

PLUGIN={'api_version':1,'id':'ocean-sensors','version':'1.0.0','label':'Mooring, ADCP and HF-radar contracts'}
CONTRACTS={
    'mooring':('Mooring','time-series','mooring-v1','Fixed location and depth; timestamps remain distinct. No inferred vertical profile.'),
    'adcp':('ADCP','profile','adcp-earth-v1','Earth-referenced east/north velocities at physical bin depths. Raw beam rotation and vessel-motion correction must occur upstream.'),
    'hf-radar':('HF radar','surface-current','hf-total-earth-v1','Total east/north surface currents at nominal depth 0 m. Radial velocities are not total vectors; no water-column reconstruction.'),
}


def parse_sensor(path, sensor):
    instrument,geometry,contract,description=CONTRACTS[sensor]
    with path.open(encoding='utf-8-sig') as stream:
        if stream.readline().strip()!=f'# ocean3d:{contract}':
            raise ValueError(f'This adapter requires the first-line contract # ocean3d:{contract}.')
    parsed=parse_delimited(path)
    out=[]
    for p in parsed:
        if p['instrument']!=instrument: raise ValueError(f'The {sensor} contract requires instrument={instrument}.')
        rows=p['samples']
        if any(r.get('longitude',p['longitude'])!=p['longitude'] or r.get('latitude',p['latitude'])!=p['latitude'] for r in rows):
            raise ValueError('Use one fixed geographic station/cell per profile_id; moving instruments need a different adapter.')
        readings=defaultdict(dict)
        for row in rows:
            key=(row.get('time',p['time']),row['depth'])
            if row['variable'] in readings[key]: raise ValueError('Duplicate variable at the same station, time and depth.')
            readings[key][row['variable']]=row
        if sensor in ('adcp','hf-radar') and any(set(v)!= {'u','v'} for v in readings.values()):
            raise ValueError('Total current data require exactly paired eastward u and northward v at each time and depth; no radial/beam conversion is inferred.')
        if sensor=='mooring' and len({r['depth'] for r in rows})!=1:
            raise ValueError('Mooring time-series contract requires one fixed depth per station ID.')
        if sensor=='hf-radar' and any(r['depth']!=0 for r in rows):
            raise ValueError('HF-radar total-current samples require nominal surface depth 0 m.')
        groups=defaultdict(list)
        for row in rows:
            groups[row.get('time',p['time']) if sensor=='adcp' else 'series'].append(row)
        for key,samples in sorted(groups.items()):
            item=deepcopy(p)
            times=sorted({r.get('time',p['time']) for r in samples})
            if len(times)>4096 or len(samples)>20_000:
                raise ValueError('One stationary series is limited to 4096 timestamps and 20,000 variable samples; split longer deployments upstream.')
            item.update(sensor_id=sensor,geometry=geometry,station_id=p['id'],
                        feature_type='profile' if sensor=='adcp' else 'timeSeries',
                        time=times[0],time_range=[times[0],times[-1]],sample_times=times,samples=samples,
                        warning=description,source=f'Ocean3D {contract} canonical table',
                        import_warnings=[*p.get('import_warnings',[]),description])
            item.pop('path',None)  # A stationary station/cell is not an underwater trajectory.
            item.pop('trajectory_id',None)
            if sensor=='adcp': item['id']=p['id']+'@'+key.replace(':','')
            item['samples'].sort(key=lambda r:(r.get('time',p['time']),r['depth'],r['variable']))
            item['depth_range']=[min(r['depth'] for r in samples),max(r['depth'] for r in samples)]
            out.append(item)
    return out


def register():
    for sensor,(label,geometry,contract,description) in CONTRACTS.items():
        register_sensor(dict(id=sensor,label=label,geometry=geometry,description=description))
        register_observation_adapter(sensor+'-csv',lambda path,sensor=sensor:parse_sensor(path,sensor),
            label=label+' · canonical table',container='text',
            detector=lambda meta,contract=contract:meta.get('header','').splitlines()[0:1]==[f'# ocean3d:{contract}'])
