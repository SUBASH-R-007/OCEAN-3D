"""Catalogue completeness, native values, source query boundaries and semantics."""
import hashlib
import json
from urllib.parse import unquote
import numpy as np
import pytest
import xarray as xr
from backend.incois_catalog import ROOT,FOLDER,read_catalog,product_for,grid_query,load_basin_models,convert_volume
from backend.incois_observations import observation_query,parse_table


def test_failed_refresh_keeps_previous_verified_source(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from backend import incois_catalog as source
    previous=tmp_path/'metadata.json';previous.write_text('{"previous":true}',encoding='utf-8')
    monkeypatch.setattr(source.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=22))
    with pytest.raises(ValueError):source.acquire(source.BASE+'/info/index.json',previous,refresh=True)
    assert json.loads(previous.read_text(encoding='utf-8'))=={'previous':True}
    assert not previous.with_suffix('.json.part').exists()


def test_every_advertised_scientific_product_and_field_is_accessible():
    catalog=read_catalog(); source=json.loads((FOLDER/'catalog-source.json').read_text(encoding='utf-8'))['table']
    assert {p['id'] for p in catalog['products']}=={r[-1] for r in source['rows'] if r[-1]!='allDatasets'}
    assert len(catalog['products'])==16
    for p in catalog['products']:
        if p['kind']=='observations':continue
        packet=json.loads((ROOT/'web/public/incois'/(p['id']+'.json')).read_text(encoding='utf-8'))
        assert set(packet['fields'])=={v['id'] for v in p['variables']}
        assert packet['time']==p['times'][-1]==p['end']
        assert p['times'][0]==p['start']
        assert all(len(a)==len(packet['longitude'])*len(packet['latitude']) for a in packet['fields'].values())
        path=FOLDER/'snapshots'/(p['id']+'.nc')
        assert hashlib.sha256(path.read_bytes()).hexdigest()==packet['source_sha256']
        with xr.open_dataset(path) as ds:
            for name,values in packet['fields'].items():
                np.testing.assert_allclose(np.array(values,dtype=float),ds[name].values.ravel(),rtol=0,atol=0,equal_nan=True)


def test_source_requests_use_exact_irregular_time_indices_native_bounds_and_bounded_strides():
    p=product_for('incois_argo_10day_McCreary')
    url,s=grid_query(p,['T_ANALYZED'],100,depth=6,bbox=[50,5,75,25])
    q=unquote(url)
    assert 'T_ANALYZED[100:1:100][6]' in q and s['longitude']['stride']==1
    global_product=product_for('AMSRE_MONTHLY_GLOBAL')
    url,s=grid_query(global_product,['SST'],0)
    assert s['longitude']['stride']==6 and s['latitude']['stride']==3
    assert s['longitude']['native_cells']==1440
    for kwargs in (dict(index=999999),dict(index=0,variables=['../escape']),dict(index=0,bbox=[-180,-90,180,90]),dict(index=0,depth=99),dict(index=0,bbox=[80,10,80,10])):
        args=dict(product=p,variables=['T_ANALYZED'],index=0);args.update(kwargs)
        with pytest.raises(ValueError):grid_query(**args)


def test_all_four_volumes_cover_the_complete_native_basin_without_temperature_relabeling():
    models=load_basin_models()
    assert len(models)==4
    for model in models:
        assert dict(model.ds.sizes)==dict(time=3,latitude=60,longitude=90,depth=24)
        np.testing.assert_equal(model.catalog()['bounds'],[30.5,-29.5,119.5,29.5])
        assert float(model.ds.depth.max())==2000
        assert 'temperature' not in model.ds
        assert 'analyzed_temperature' in model.ds
        if 'vam' in model.id:assert 'temperature_spread' not in model.ds
        packet=model.volume('analyzed_temperature',2,8,bbox=(50,5,75,25))
        assert packet['valid_cells']>0 and packet['bbox']==[50,5,75,25]


def test_basin_thermal_packet_keeps_exact_source_values_masks_and_depth_brackets():
    packet=json.loads((ROOT/'web/public/demo/incois-mnt-mccreary-latest/thermal-structure.json').read_text(encoding='utf-8'))
    path=FOLDER/'incois-mnt-mccreary-latest-source.nc'
    with xr.open_dataset(path) as ds:
        for i,frame in enumerate(packet['frames']):
            for target,source in [('temperature','T_ANALYZED'),('local_count','T_BOXOBS'),('influence_count','T_ROIOBS')]:
                np.testing.assert_allclose(np.array(frame[target],dtype=float),ds[source].isel(time=i).values.ravel(),rtol=0,atol=0,equal_nan=True)


def test_observations_keep_channels_and_quality_flags_and_bound_downloads():
    packet=json.loads((ROOT/'web/public/incois/Indian_ARGO_Floats.json').read_text(encoding='utf-8'))
    assert packet['source_rows']==sum(len(p['levels']) for p in packet['profiles'])>0
    for profile in packet['profiles']:
        for level in profile['levels']:
            assert set(level)=={'raw','adjusted'}
            for c in level.values():assert c['depth'] is None or c['depth']>=0
    with pytest.raises(ValueError):observation_query('2025-01-01T00:00:00Z','2025-02-01T00:00:00Z')
    with pytest.raises(ValueError):observation_query('2026-01-01T00:00:00Z','2026-01-02T00:00:00Z')
    with pytest.raises(ValueError):observation_query('2025-01-01','2025-01-02')
    with pytest.raises(ValueError):observation_query('2025-01-01T00:00:00Z','2025-01-02T00:00:00Z',[170,-10,-170,10])
