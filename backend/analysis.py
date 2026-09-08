import numpy as np
from .science import Model, clean

def compare(model: Model, profile, variable, qc='strict', max_gap_hours=48):
    rows = [dict(r) for r in profile['samples'] if r['variable']==variable]
    allowed = {1} if qc=='strict' else {1,2}
    accepted = [r for r in rows if r['qc'] in allowed and r['value'] is not None]
    supported = variable in model.ds.data_vars
    values = model.sample(variable,[r.get('longitude',profile['longitude']) for r in accepted],[r.get('latitude',profile['latitude']) for r in accepted],[r['depth'] for r in accepted],[r.get('time',profile['time']).replace('Z','') for r in accepted],max_gap_hours) if accepted and supported else np.full(len(accepted), np.nan)
    pairs=[]
    for row, value in zip(accepted, values):
        row['model'] = float(value) if np.isfinite(value) else None
        row['residual'] = row['model']-row['value'] if row['model'] is not None else None
        pairs.append(row)
    residuals=np.asarray([p['residual'] for p in pairs if p['residual'] is not None])
    reason = None
    if not supported:
        reason = ('This model does not supply temperature with the same potential-temperature definition. The observation is shown independently.' if variable=='temperature' else 'This model does not supply the selected observation variable. The observation is shown independently.')
    elif accepted and not len(residuals):
        reason = 'No model match at this observation position, time and accepted depths. The observation remains visible; no extrapolation is performed.'
    return dict(profile={k:v for k,v in profile.items() if k!='samples'},variable=variable,pairs=pairs,samples=rows,comparison_reason=reason,
                metrics=dict(count=len(residuals),total=len(rows),qc_excluded=len(rows)-len(accepted),unmatched=len(accepted)-len(residuals),bias=float(residuals.mean()) if len(residuals) else None,rmse=float(np.sqrt(np.mean(residuals**2))) if len(residuals) else None,mae=float(np.mean(np.abs(residuals))) if len(residuals) else None),
                method=dict(interpolation='linear longitude, latitude, depth and time; no extrapolation; invalid corners propagate',residual='model minus observation',qc_flags=sorted(allowed),max_time_gap_hours=max_gap_hours),provenance=model.provenance,
                limitations=['Agreement is not independent model skill when observations may have been assimilated.','Instrument error is not total uncertainty; no confidence percentage is inferred.'])

def coverage(model, profiles, variable, index, qc='strict'):
    cat=model.catalog(); west,south,east,north=cat['bounds']
    date=np.datetime64(cat['times'][index].replace('Z',''))
    eligible=[p for p in profiles if any(s['variable']==variable and s['qc'] in ({1} if qc=='strict' else {1,2}) and s['value'] is not None and abs((np.datetime64(s.get('time',p['time']).replace('Z',''))-date)/np.timedelta64(1,'h'))<=24 for s in p['samples'])]
    cells=[]
    for lat in np.linspace(south,north,8):
        for lon in np.linspace(west,east,8):
            # Nearest profile distance: coverage indicator, not a calibrated error estimate.
            distances=[]
            for p in eligible:
                a,b=np.radians([lat,p['latitude']]);dl=np.radians(lon-p['longitude'])
                h=np.sin((a-b)/2)**2+np.cos(a)*np.cos(b)*np.sin(dl/2)**2
                distances.append(6371*2*np.arcsin(np.sqrt(np.clip(h,0,1))))
            valid=model.sample(variable,lon,lat,float(model.ds.depth.min()),cat['times'][index].replace('Z',''))[0]
            cells.append(dict(longitude=round(float(lon),3),latitude=round(float(lat),3),distance_km=round(min(distances),1) if distances and np.isfinite(valid) else None,ocean=bool(np.isfinite(valid))))
    ranked=sorted([c for c in cells if c['distance_km'] is not None],key=lambda c:c['distance_km'],reverse=True)
    return dict(cells=cells,eligible_profiles=len(eligible),time_window_hours=24,priority=ranked[:3],method='Great-circle distance to QC-eligible profiles within ±24 h; surface-valid cells only. Distance is not uncertainty or a vessel route.')

def transect(model, variable, index, start, end):
    lon=np.linspace(start[0],end[0],48);lat=np.linspace(start[1],end[1],48)
    depths=np.linspace(float(model.ds.depth.min()),float(model.ds.depth.max()),32)
    z,x=np.meshgrid(depths,np.arange(48),indexing='ij')
    vals=model.sample(variable,lon[x],lat[x],z,model.ds.time.values[index]).reshape(32,48)
    return dict(longitudes=clean(lon),latitudes=clean(lat),depths=clean(depths),values=clean(vals),method='Straight line in longitude/latitude; 4D interpolation without extrapolation; not a geodesic navigation path.')
