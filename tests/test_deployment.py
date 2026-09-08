import json
import os
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from backend import api
from backend.server import ServerSettings


@pytest.mark.parametrize('env', [
    {'OCEAN_MODE':'invalid'}, {'OCEAN_WORKERS':'2'}, {'WEB_CONCURRENCY':'2'},
    {'OCEAN_MODE':'readonly','OCEAN_WORKERS':'0'}, {'OCEAN_MAX_ACTIVE':'bad'},
    {'OCEAN_MAX_ACTIVE':'33'}, {'OCEAN_PORT':'70000'},
])
def test_unsafe_server_settings_fail_before_startup(env):
    with pytest.raises(ValueError): ServerSettings.from_env(env)


def test_readonly_worker_settings():
    config=ServerSettings.from_env({'OCEAN_MODE':'readonly','OCEAN_WORKERS':'2','OCEAN_MAX_ACTIVE':'3'})
    assert config.readonly and config.workers==2 and config.max_active==3
    assert not ServerSettings.from_env({}).readonly


def test_readonly_serving_blocks_mutations_and_remote_io(tmp_path,monkeypatch):
    data=tmp_path/'uncreated-imports'
    monkeypatch.setattr(api,'DATA',data)
    monkeypatch.setattr(api,'SETTINGS',replace(api.SETTINGS,mode='readonly',workers=2))
    with TestClient(api.app) as client:
        ready=client.get('/api/ready')
        assert ready.status_code==200 and ready.json()['status']=='ready'
        assert ready.json()['capabilities']=={'imports':False,'upstream_acquisition':False}
        assert client.get('/api/catalog').status_code==200
        frame=client.get('/api/volume.bin?resolution=8')
        assert frame.content[:4]==b'OCV1' and frame.headers['x-ocean-worker']==str(os.getpid())
        assert client.post('/api/transect',json={'start':[84,10],'end':[85,11]}).status_code==200
        for route in ('/api/import','/api/import/inspect','/api/incois/open'):
            assert client.post(route,content=b'invalid body rejected before parsing').status_code==403
        assert client.get('/api/incois/grid?product=bad').status_code==403
        assert not data.exists()
        runtime=client.get('/api/runtime').json()['deployment']
        assert runtime['mode']=='readonly' and runtime['configured_workers']==2
        assert len(runtime['startup_catalog_revision'])==64
    assert api.app.state.ready is False


def test_readiness_catches_failed_restore_and_health_remains_alive(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'DATA',tmp_path)
    (tmp_path/'invalid.json').write_text(json.dumps({'id':'missing','file':'absent.nc','kind':'model','title':'Missing'}))
    with TestClient(api.app) as client:
        assert client.get('/api/health').status_code==200
        ready=client.get('/api/ready')
        assert ready.status_code==503 and ready.headers['retry-after']=='2'
        assert ready.json()['restore_errors']==1 and ready.json()['status']=='not-ready'


def test_api_reference_and_probes_work_under_the_proxy_prefix(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'DATA',tmp_path)
    with TestClient(api.app) as client:
        assert client.get('/api/docs').status_code==200
        schema=client.get('/api/openapi.json').json()
        assert schema['info']['title']=='Ocean3D scientific API'
        assert '/api/volume.bin' in schema['paths'] and '/api/ready' in schema['paths']
        monkeypatch.setenv('OCEAN_API_TOKEN','fixture-token')
        assert client.get('/api/ready').status_code==200
        assert client.get('/api/openapi.json').status_code==401
        assert client.get('/api/openapi.json',headers={'Authorization':'Bearer fixture-token'}).status_code==200
        for _ in range(api.MAX_ACTIVE): assert api.WORK_SLOTS.acquire(False)
        try:
            assert client.get('/api/volume',headers={'Authorization':'Bearer fixture-token'}).status_code==503
            assert client.get('/api/ready').status_code==200
        finally:
            for _ in range(api.MAX_ACTIVE): api.WORK_SLOTS.release()
