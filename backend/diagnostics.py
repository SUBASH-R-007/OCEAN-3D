"""Transparent water-column diagnostics. These are diagnostics, not forecasts.

TEOS-10 derives Absolute Salinity, Conservative Temperature and sigma0. MLD
uses a 10 m reference and 0.03 kg/m3 density increase; temperature departure
uses |theta(z)-theta(10)| >= 0.2 C (de Boyer Montegut et al., 2004).
"""
from __future__ import annotations
import numpy as np
import gsw
from .science import clean

SOURCES = [
    'https://www.teos-10.org/pubs/gsw/html/gsw_CT_from_pt.html',
    'https://www.teos-10.org/pubs/gsw/html/gsw_sigma0.html',
    'https://doi.org/10.1029/2004JC002378',
    'https://doi.org/10.1029/2006JC003953',
]


def crossing(depth, values, reference, threshold, absolute=False, max_gap=150):
    """First threshold crossing, interpolated only across contiguous support.

    A gap before the first crossing censors the result: it cannot be skipped
    because it might contain an earlier crossing. 'not_reached' is not zero.
    """
    depth = np.asarray(depth, dtype=float)
    values = np.asarray(values, dtype=float)
    if len(depth) < 2 or np.any(np.diff(depth) <= 0):
        raise ValueError('Diagnostic depths must be unique and increasing.')
    base = int(np.searchsorted(depth, reference))
    if base >= len(depth) or depth[base] != reference or not np.isfinite(values[base]):
        return dict(depth_m=None, status='reference_unavailable', bracket_m=None)
    ref = values[base]
    previous = 0.
    for i in range(base+1, len(depth)):
        if not np.isfinite(values[i]) or depth[i]-depth[i-1] > max_gap:
            return dict(depth_m=None, status='gap_before_crossing', bracket_m=None)
        current = abs(values[i]-ref) if absolute else values[i]-ref
        if current >= threshold:
            fraction = (threshold-previous)/(current-previous)
            z = depth[i-1] + fraction*(depth[i]-depth[i-1])
            return dict(depth_m=round(float(z), 3), status='resolved',
                        bracket_m=[float(depth[i-1]), float(depth[i])])
        previous = current
    return dict(depth_m=None, status='not_reached_in_sampled_column', bracket_m=None)


def column_diagnostics(depth, theta, sp, lon, lat, reference=10., density_delta=.03, temperature_delta=.2):
    z = np.asarray(depth, dtype=float)
    theta = np.asarray(theta, dtype=float)
    sp = np.asarray(sp, dtype=float)
    pressure = gsw.p_from_z(-z, lat)
    sa = gsw.SA_from_SP(sp, pressure, lon, lat)
    ct = gsw.CT_from_pt(sa, theta)
    sigma = gsw.sigma0(sa, ct)
    valid = np.isfinite(theta) & np.isfinite(sp) & (sp >= 0) & gsw.infunnel(sa, ct, pressure).astype(bool)
    sigma = np.where(valid, sigma, np.nan)
    density = crossing(z, sigma, reference, density_delta)
    thermal = crossing(z, np.where(valid, theta, np.nan), reference, temperature_delta, absolute=True)
    barrier = dict(signed_thickness_m=None, status='reference_unavailable', equivalent_density_delta_kg_m3=None)
    ref_idx=np.flatnonzero(z==reference)
    if len(ref_idx) and valid[ref_idx[0]]:
        i=ref_idx[0]
        equivalent=float(gsw.sigma0(sa[i], gsw.CT_from_pt(sa[i], theta[i]-.2))-sigma[i])
        cool=crossing(z,np.where(valid,-theta,np.nan),reference,.2)
        equivalent_depth=crossing(z,sigma,reference,equivalent)
        resolved=cool['depth_m'] is not None and equivalent_depth['depth_m'] is not None
        thickness=round(cool['depth_m']-equivalent_depth['depth_m'],3) if resolved else None
        barrier=dict(signed_thickness_m=thickness,status=('barrier' if thickness>0 else 'compensated' if thickness<0 else 'coincident') if resolved else 'unresolved',
                     equivalent_density_delta_kg_m3=equivalent,cooling_depth=cool,density_depth=equivalent_depth,
                     method='TEOS-10 adaptation of de Boyer Montegut 2007: first 0.2 C cooling depth minus density depth using the equivalent threshold at fixed reference SA; signed differences retained.')
    with np.errstate(invalid='ignore', divide='ignore'):
        n2,p_mid=gsw.Nsquared(np.where(valid,sa,np.nan),np.where(valid,ct,np.nan),pressure,lat)
    n2=np.where((np.diff(z)<=150)&valid[:-1]&valid[1:],n2,np.nan)
    # Show resolution sensitivity, not a statistical confidence interval.
    sensitivity = [dict(delta_kg_m3=d, **crossing(z, sigma, reference, d)) for d in (.02, .03, .05)]
    rows = [dict(depth=float(a), theta=b, salinity=c, sigma0=d, conservative_temperature=e)
            for a,b,c,d,e in zip(z, clean(theta), clean(sp), clean(sigma), clean(np.where(valid,ct,np.nan)))]
    return dict(density_mld=density, temperature_departure_depth=thermal, barrier_layer=barrier,
                stratification=dict(depths=clean(-gsw.z_from_p(p_mid,lat)),n_squared_s2=clean(n2,9),
                                    method='TEOS-10 N² at pressure midpoints; negative values retained; gaps above 150 m excluded.'),
                density_threshold_sensitivity=sensitivity, rows=rows,
                valid_levels=int(valid.sum()), total_levels=len(z),
                method=dict(reference_depth_m=reference, density_increase_kg_m3=density_delta,
                            absolute_temperature_departure_c=temperature_delta, maximum_vertical_gap_m=150,
                            equation_of_state='TEOS-10: depth→pressure; SP→SA; theta(0 dbar)→CT; sigma0(SA,CT)',
                            crossing='First threshold crossing, linear between adjacent valid levels; no extrapolation'),
                limitations=['Threshold sensitivity is not uncertainty or a confidence interval.',
                             'A crossing bracket indicates native vertical resolution; interpolation does not add observations.',
                             'Layer diagnostics are not an operational cyclone-risk forecast.',
                             'Values outside the TEOS-10 oceanographic funnel are excluded.'], sources=SOURCES)


def diagnose_model(model, lon, lat, index, reference=10., density_delta=.03):
    if not {'temperature', 'salinity'}.issubset(model.ds):
        raise ValueError('Density diagnostics require both potential temperature and practical salinity.')
    if index < 0 or index >= model.ds.sizes['time']:
        raise ValueError('Time index unavailable.')
    native = model.ds.depth.values.astype(float)
    if len(native) > 2000:
        raise ValueError('Diagnostic column exceeds 2000 native depth levels.')
    # Adding the reference uses bounded interpolation, not extrapolation above the data.
    depth = np.unique(np.concatenate([native, [reference]]))
    date = model.ds.time.values[index]
    theta = model.sample('temperature', lon, lat, depth, date)
    sp = model.sample('salinity', lon, lat, depth, date)
    right=np.searchsorted(native,reference)
    if 0<right<len(native) and native[right]!=reference and native[right]-native[right-1]>150:
        theta[depth==reference]=np.nan;sp[depth==reference]=np.nan
    result = column_diagnostics(depth, theta, sp, lon, lat, reference, density_delta)
    return dict(model_id=model.id, longitude=lon, latitude=lat,
                time=model.catalog()['times'][index], provenance=model.provenance, **result)


def diagnose_observation(profile, reference=10., density_delta=.03):
    """Use paired QC1 levels; never bridge rejected rows for first-crossing analysis."""
    by_depth = {}
    for row in profile['samples']:
        if row['variable'] not in ('temperature','salinity'):
            continue
        values = by_depth.setdefault(row['depth'], {})
        if row['variable'] in values:
            raise ValueError('Duplicate observation depth/variable cannot define a diagnostic column.')
        pressure_ok = row.get('pressure_error_dbar') is None or row['pressure_error_dbar'] <= 20
        values[row['variable']] = row['value'] if row['qc']==1 and row['value'] is not None and pressure_ok else np.nan
    z = np.array(sorted(by_depth), dtype=float)
    if len(z) < 2:
        raise ValueError('Observation diagnostics need at least two paired temperature/salinity depths.')
    theta = np.array([by_depth[d].get('temperature', np.nan) for d in z])
    sal = np.array([by_depth[d].get('salinity', np.nan) for d in z])
    from .science import multilinear
    target = np.unique(np.concatenate([z, [reference]]))
    theta = multilinear([z], theta, target[:,None])
    sal = multilinear([z], sal, target[:,None])
    right=np.searchsorted(z,reference)
    if 0<right<len(z) and z[right]!=reference and z[right]-z[right-1]>150:
        theta[target==reference]=np.nan;sal[target==reference]=np.nan
    result = column_diagnostics(target,theta,sal,profile['longitude'],profile['latitude'],reference,density_delta)
    result['limitations'].append('QC 1 only; supplied pressure errors above 20 dbar excluded. Missing pressure errors cannot establish pressure accuracy; adjusted delayed-mode observations are preferred.')
    return dict(profile_id=profile['id'], time=profile['time'], data_mode=profile['data_mode'],
                synthetic=profile['synthetic'], **result)
