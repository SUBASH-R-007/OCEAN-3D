from fastapi.testclient import TestClient
from backend import api
import pytest

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'DATA',tmp_path)
    with TestClient(api.app) as client:yield client

def test_catalog_volume_and_error_contract(client):
    assert client.get('/api/health').json()['status']=='ok'
    cat=client.get('/api/catalog').json()
    assert cat['models'][0]['provenance']['synthetic'] is True
    r=client.get('/api/volume?resolution=8')
    assert r.status_code==200 and len(r.json()['values'])<=512
    assert client.get('/api/volume?resolution=200').status_code==422
    assert client.get('/api/volume?model=missing').status_code==404
    assert client.get('/api/volume?variable=unknown').status_code==422
    assert client.get('/api/volume?index=999').status_code==422

def test_profile_policy_and_invalid_input(client):
    p=client.get('/api/profiles/DEMO-ARGO-01').json()
    assert p['metrics']['qc_excluded']==2
    assert client.get('/api/profiles/DEMO-ARGO-01?qc=all').status_code==422
    assert client.get('/api/profiles/missing').status_code==404
    assert client.post('/api/transect',json={'start':[84,10],'end':[90,18]}).status_code==200

def test_import_persistence_and_rejection(client,tmp_path):
    invalid=client.post('/api/import?kind=model',files={'file':('bad.nc',b'not netcdf')})
    assert invalid.status_code==422 and 'not a readable NetCDF' in invalid.json()['detail']
    assert not list(tmp_path.glob('*.nc'))
    csv=b'profile_id,instrument,longitude,latitude,time,depth,variable,value,qc\nTEST,CTD,85,14,2025-09-03T12:00:00Z,10,temperature,28,1\n'
    response=client.post('/api/import?kind=csv',files={'file':('../../unsafe.csv',csv)})
    assert response.status_code==201
    identity=response.json()['id'];assert len(response.json()['sha256'])==64
    assert (tmp_path/(identity+'.json')).exists()
    p=client.get('/api/profiles/'+identity+':TEST')
    assert p.status_code==200 and p.json()['metrics']['count']==1

def test_optional_api_token(client,monkeypatch):
    monkeypatch.setenv('OCEAN_API_TOKEN','test-token')
    assert client.get('/api/health').status_code==200
    assert client.get('/api/catalog').status_code==401
    assert client.get('/api/catalog',headers={'Authorization':'Bearer test-token'}).status_code==200


def test_diagnostics_and_interchange_api_contract(client):
    result=client.get('/api/diagnostics?profile=DEMO-ARGO-01')
    assert result.status_code==200 and result.json()['density_mld']['status']=='resolved'
    assert client.get('/api/diagnostics?profile=missing').status_code==404
    cov=client.get('/api/export/column.covjson')
    assert cov.status_code==200 and 'application/prs.coverage+json' in cov.headers['content-type']
    assert cov.json()['type']=='Coverage'
    nc=client.get('/api/export/subset.nc?maximum_depth=200')
    assert nc.status_code==200 and nc.content[:3]==b'CDF'
    assert client.get('/api/export/subset.nc?bbox=bad').status_code==422
    assert client.get('/api/export/subset.nc?bbox=0,0,1,1').status_code==422
    upper=client.get('/api/volume?maximum_depth=500').json()
    full=client.get('/api/volume').json()
    assert upper['axes']['depth'][-1]==500 and full['axes']['depth'][-1]==1000

def test_netcdf_import_and_restart_restore(client,tmp_path):
    from backend.demo import build_demo
    model,_=build_demo()
    source=tmp_path/'fixture.nc';model.ds.to_netcdf(source)
    response=client.post('/api/import?kind=model',files={'file':('fixture.nc',source.read_bytes())})
    assert response.status_code==201,response.text
    identity=response.json()['id']
    result=client.get('/api/volume',params={'model':identity,'resolution':8})
    assert result.status_code==200 and result.json()['provenance']['synthetic'] is True
    api.MODELS.pop(identity).close()
    # Restore exactly from persisted manifest, as the next server startup does.
    import json
    manifest=json.loads((tmp_path/(identity+'.json')).read_text())
    api.register(tmp_path/manifest['file'],manifest['kind'],manifest['id'],manifest['title'])
    assert client.get('/api/volume',params={'model':identity,'resolution':8}).status_code==200
