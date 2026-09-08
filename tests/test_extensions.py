import io
import hashlib
import json
import xml.etree.ElementTree as ET
import numpy as np
import pytest
import xarray as xr
from fastapi.testclient import TestClient
from backend import api
from backend.cf_profiles import parse_cf_profiles
from backend.plugins import register_variable, load_variable_plugins
from backend.science import VARIABLES, normalize, Model
from backend.exports import subset_netcdf
from scripts.build_cf_example import example


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'DATA',tmp_path/'imports')
    with TestClient(api.app) as client: yield client


def write_example(tmp_path, ds=None):
    path=tmp_path/'mission.nc'; (example() if ds is None else ds).to_netcdf(path,engine='scipy');return path


def test_cf_trajectory_preserves_native_samples_qc_positions_and_mission(tmp_path):
    p=parse_cf_profiles(write_example(tmp_path)); source=example()
    assert len(p)==4 and p[0]['trajectory_id']=='SYNTHETIC-GLIDER'
    assert p[0]['longitude'] != p[-1]['longitude'] and p[0]['time'] != p[-1]['time']
    assert all(x['synthetic'] for x in p)
    temp=[r for r in p[0]['samples'] if r['variable']=='temperature']
    assert len(temp)==7 and temp[5]['qc']==4
    np.testing.assert_allclose([r['value'] for r in temp], source.thetao.values[:7])
    assert len(p[0]['samples'])==21


def test_cf_missing_quality_is_unknown_and_bad_metadata_rejected(tmp_path):
    ds=example();ds.thetao.attrs.pop('ancillary_variables')
    parsed=parse_cf_profiles(write_example(tmp_path,ds))
    assert all(r['qc']==0 for r in parsed[0]['samples'] if r['variable']=='temperature')
    for mutate in [lambda d: d.row_size.values.__setitem__(0,6), lambda d: d.trajectory_index.values.__setitem__(0,5), lambda d: d.longitude.attrs.__setitem__('units','radians'), lambda d: d.thetao.attrs.__setitem__('units','K')]:
        d=example();mutate(d)
        with pytest.raises(ValueError):parse_cf_profiles(write_example(tmp_path,d))


def test_cf_indexed_and_incomplete_profile_layouts(tmp_path):
    ds=example().drop_vars(['row_size','trajectory_id','trajectory_index']);ds.attrs['featureType']='profile'
    ds['profile_index']=('obs',np.repeat(np.arange(4),7),{'instance_dimension':'profile'})
    assert len(parse_cf_profiles(write_example(tmp_path,ds)))==4
    ds=ds.drop_vars('profile_index'); ds=ds.rename_dims({'obs':'unused'})
    for key in ['depth','thetao','thetao_qc','so','so_qc','chl','chl_qc']:
        values=ds[key].values.reshape(4,7); attrs=ds[key].attrs;ds=ds.drop_vars(key);ds[key]=(('profile','level'),values,attrs)
    ds.depth.values[3,-1]=np.nan
    result=parse_cf_profiles(write_example(tmp_path,ds));assert len(result[-1]['samples'])==18


def test_cf_in_situ_conversion_requires_salinity_and_preserves_qc(tmp_path):
    import gsw
    ds=example();ds.thetao.attrs['standard_name']='sea_water_temperature';ds.so_qc.values[2]=4
    profiles=parse_cf_profiles(write_example(tmp_path,ds));rows=[r for r in profiles[0]['samples'] if r['variable']=='temperature']
    pressure=gsw.p_from_z(-ds.depth.values[:7],float(ds.latitude[0]))
    expected=gsw.pt0_from_t(gsw.SA_from_SP(ds.so.values[:7],pressure,float(ds.longitude[0]),float(ds.latitude[0])),ds.thetao.values[:7],pressure)
    np.testing.assert_allclose([r['value'] for r in rows],expected)
    assert rows[2]['qc']==4 and rows[2]['source_in_situ_temperature']==ds.thetao.values[2]
    ds=ds.drop_vars('so')
    with pytest.raises(ValueError,match='requires colocated practical salinity'):parse_cf_profiles(write_example(tmp_path,ds))


def test_variable_plugin_end_to_end_and_conflict_atomicity(tmp_path):
    from backend.demo import build_demo
    definition=json.loads((api.ROOT/'config/variables.example.json').read_text())[0]
    try:
        register_variable(definition)
        source,_=build_demo();ds=source.ds.copy();ds['o2']=ds.temperature*0+200
        ds.o2.attrs={'standard_name':definition['standard'],'units':'mmol m-3'}
        normalized=normalize(ds);m=Model('oxygen-test',normalized,{'title':'fixture','synthetic':True})
        assert m.catalog()['variables'][-1]['id']=='oxygen'
        assert max(v for v in m.volume('oxygen',0,8)['values'] if v is not None)==200
        with xr.open_dataset(io.BytesIO(subset_netcdf(m,'oxygen',0)),engine='scipy') as exported:
            assert exported.oxygen.attrs['units']=='mmol m-3'
        ds.o2.attrs['units']='mol m-3'
        with pytest.raises(ValueError):normalize(ds)
        with pytest.raises(ValueError):register_variable(definition)
    finally: VARIABLES.pop('oxygen',None)
    path=tmp_path/'plugins.json';path.write_text(json.dumps([definition,definition]))
    with pytest.raises(ValueError):load_variable_plugins(path)
    assert 'oxygen' not in VARIABLES


def test_cf_api_import_idempotence_restore_and_comparison(client,tmp_path):
    payload=write_example(tmp_path).read_bytes();digest=hashlib.sha256(payload).hexdigest()
    def send():return client.post('/api/import?kind=cf-profile',files={'file':('mission.nc',payload)},headers={'Idempotency-Key':digest+':cf-profile'})
    first=send();assert first.status_code==201,first.text
    second=send();assert second.json()['id']==first.json()['id'] and second.json()['duplicate']
    identity=first.json()['id']
    cat=client.get('/api/catalog').json();ps=[p for p in cat['profiles'] if p['id'].startswith(identity+':')]
    assert len(ps)==4 and ps[0]['trajectory_id'].startswith(identity+':')
    response=client.get('/api/profiles/'+ps[0]['id'],params={'model':'demo-bob','variable':'temperature'})
    assert response.json()['metrics']['count']==6 and response.json()['metrics']['qc_excluded']==1
    info=json.loads((api.DATA/(identity+'.json')).read_text())
    for p in ps:api.PROFILES.pop(p['id'])
    api.register(api.DATA/info['file'],info['kind'],identity)
    assert len([p for p in api.PROFILES if p.startswith(identity+':')])==4
    assert client.post('/api/import?kind=../unsafe',files={'file':('a',payload)}).status_code==422


def map_params():
    return dict(SERVICE='WMS',VERSION='1.3.0',REQUEST='GetMap',LAYERS='demo-bob:temperature',STYLES='',CRS='CRS:84',BBOX='84,12,87,16',WIDTH='20',HEIGHT='16',FORMAT='image/png',ELEVATION='-100',TIME='2025-09-03T12:00:00Z')


def test_wms_axis_order_feature_values_mask_and_exceptions(client):
    p=map_params();m=api.MODELS['demo-bob'];p['TIME']=m.catalog()['times'][2];p['ELEVATION']=str(-m.catalog()['depths'][2])
    a=client.get('/api/ogc/wms',params=p);assert a.status_code==200,a.text[:300] if a.status_code!=200 else ''
    assert a.content[:8]==b'\x89PNG\r\n\x1a\n'
    b=client.get('/api/ogc/wms',params={**p,'CRS':'EPSG:4326','BBOX':'12,84,16,87'})
    assert a.content==b.content
    q={**p,'REQUEST':'GetFeatureInfo','QUERY_LAYERS':p['LAYERS'],'INFO_FORMAT':'application/json','I':'10','J':'8'}
    info=client.get('/api/ogc/wms',params=q).json()
    expected=m.sample('temperature',info['longitude'],info['latitude'],info['depth'],m.ds.time.values[2])[0]
    assert info['value']==pytest.approx(expected)
    outside=client.get('/api/ogc/wms',params={**q,'BBOX':'0,0,1,1'}).json();assert outside['value'] is None
    for patch in [{'ELEVATION':'100'},{'WIDTH':'100000'},{'TIME':'1900-01-01T00:00:00Z'},{'CRS':'EPSG:3857'},{'STYLES':'missing'}]:
        r=client.get('/api/ogc/wms',params={**p,**patch});assert r.status_code==400
        assert ET.fromstring(r.content).find('{http://www.opengis.net/ogc}ServiceException') is not None


def test_wcs_describe_and_native_coverage_roundtrip(client):
    base=dict(SERVICE='WCS',VERSION='1.0.0');identifier='demo-bob:temperature:2'
    desc=client.get('/api/ogc/wcs',params={**base,'REQUEST':'DescribeCoverage','COVERAGE':identifier})
    assert desc.status_code==200 and b'CoverageOffering' in desc.content
    m=api.MODELS['demo-bob'];params={**base,'REQUEST':'GetCoverage','COVERAGE':identifier,'CRS':'EPSG:4326','BBOX':'84,12,87,16','FORMAT':'NetCDF','TIME':m.catalog()['times'][2]}
    r=client.get('/api/ogc/wcs',params=params);assert r.status_code==200,r.text[:200] if r.status_code!=200 else ''
    with xr.open_dataset(io.BytesIO(r.content),engine='scipy') as ds:
        expected=m.ds.temperature.isel(time=slice(2,3),depth=slice(2,3)).sel(longitude=slice(84,87),latitude=slice(12,16))
        np.testing.assert_allclose(ds.temperature,expected,equal_nan=True)
        assert ds.sizes['depth']==1 and ds.depth.values[0]==m.ds.depth.values[2]
    assert client.get('/api/ogc/wcs',params={**params,'RESX':'1'}).status_code==400
    assert client.get('/api/ogc/wcs',params={**params,'BBOX':'0,0,1,1'}).status_code==400
    for service in ['WMS','WCS']:
        cap=client.get('/api/ogc/'+service.lower(),params={'service':service,'request':'GetCapabilities'})
        assert cap.status_code==200
        ET.fromstring(cap.content)
