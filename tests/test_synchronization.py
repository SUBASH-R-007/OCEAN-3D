import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import shutil
import pytest
import xarray as xr
from fastapi.testclient import TestClient
from backend import api,incois_catalog as source
from backend.science import Model,normalize
from backend.synchronization import Synchronizer,public_profiles


@pytest.fixture
def rig(tmp_path,monkeypatch):
    source.reset_catalog()
    catalog=source.read_catalog('bundled')
    catalog['products']=[p for p in catalog['products'] if p['id'] in ('incois_argo_mnt_McCreary','Indian_ARGO_Floats')]
    for p in catalog['products']:p.pop('snapshot',None);p.pop('model_id',None)
    def acquire(url,path,*args,**kwargs):
        path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source.FOLDER/path.name,path)
        return path
    def build(folder=None,**kwargs):
        for p in catalog['products']:
            if p['kind']!='observations':shutil.copyfile(source.FOLDER/(p['id']+'-axes.nc'),folder/(p['id']+'-axes.nc'))
        return deepcopy(catalog)
    def grid(product,*args,**kwargs):
        return dict(product=product['id'],time=product['end'],retrieved_at='2026-09-08T00:00:00Z',source_sha256='a'*64,fields={'T_ANALYZED':[28,None]},longitude=[85,86],latitude=[14])
    def volume(product,*args):
        path=source.FOLDER/'incois-mnt-mccreary-latest.nc'
        with xr.open_dataset(path) as ds:data=normalize(ds).load()
        return Model('sync-fixture',data,dict(title='Synchronization test',synthetic=False,source='Test fixture')),path
    from backend import incois_observations
    packet=json.loads((source.ROOT/'web/public/incois/Indian_ARGO_Floats.json').read_text(encoding='utf-8'))
    monkeypatch.setattr(source,'acquire',acquire);monkeypatch.setattr(source,'build_catalog',build)
    monkeypatch.setattr(source,'grid_packet',grid);monkeypatch.setattr(source,'acquire_volume',volume)
    monkeypatch.setattr(incois_observations,'observation_packet',lambda *a,**k:deepcopy(packet))
    received=[]
    def publish(models,profiles):
        received.append(([(m.id,m.ds.sizes['depth']) for m in models],profiles))
        for m in models:m.close()
    manager=Synchronizer(tmp_path/'sync',publish)
    yield manager,received
    source.reset_catalog()


def test_success_persists_validated_catalog_models_profiles_and_restores(rig):
    manager,received=rig;manager.run()
    assert manager.status()['status']=='ok',manager.status()
    assert received[-1][0]==[('sync-fixture',24)]
    assert received[-1][1] and all(p['id'].startswith('sync-argo-') for p in received[-1][1])
    revision=source.read_catalog()['revision']
    path=manager.snapshot_path(revision,'incois_argo_mnt_McCreary')
    assert json.loads(path.read_text())['fields']['T_ANALYZED']==[28,None]
    source.reset_catalog();manager.restore()
    assert source.read_catalog()['revision']==revision and len(received)==2


def test_failed_metadata_check_keeps_previous_generation_and_records_failure(rig,monkeypatch):
    manager,received=rig;manager.run();before=source.read_catalog()['revision']
    monkeypatch.setattr(source,'acquire',lambda *a,**k:(_ for _ in ()).throw(ValueError('Upstream unavailable')))
    manager.run()
    assert manager.status()['status']=='error' and 'Upstream unavailable' in manager.status()['error']
    assert source.read_catalog()['revision']==before and len(received)==1
    assert len(list((manager.folder/'revisions').iterdir()))==1


def test_partial_refresh_retains_prior_packet_with_original_date(rig,monkeypatch):
    manager,_=rig;manager.run()
    monkeypatch.setattr(source,'grid_packet',lambda *a,**k:(_ for _ in ()).throw(ValueError('Source timeout')))
    manager.run()
    assert manager.status()['status']=='partial'
    p=source.product_for('incois_argo_mnt_McCreary')
    assert p['sync_error']=='Source timeout' and p['model_id']=='sync-fixture'
    packet=json.loads(manager.snapshot_path(p['catalog_revision'],p['id']).read_text())
    assert packet['retrieved_at']=='2026-09-08T00:00:00Z'
    assert manager.status()['products'][0].get('retained_data_time') or manager.status()['products'][1].get('retained_data_time')


def test_restore_rejects_corruption_and_snapshot_paths_cannot_escape(rig):
    manager,_=rig;manager.run()
    with pytest.raises(ValueError):manager.snapshot_path('../escape','anything')
    (manager.previous/'profiles.json').write_text('[]')
    with pytest.raises(ValueError,match='checksum'):manager.restore()


def test_old_product_indices_keep_their_axes_generation(rig):
    manager,_=rig;manager.run();old=source.product_for('incois_argo_mnt_McCreary')
    manager.run();current=source.product_for(old['id'])
    assert old['catalog_revision']!=current['catalog_revision']
    assert source.axes_for(old)['time'].tolist()==source.axes_for(current)['time'].tolist()
    assert source.product_for(old['id'],old['catalog_revision'])==old
    source.CATALOG_REVISIONS.pop(old['catalog_revision'])
    with pytest.raises(ValueError,match='expired'):source.axes_for(old)


def test_pointer_write_failure_does_not_publish_or_remove_previous_data(rig,monkeypatch):
    from backend import synchronization
    manager,received=rig;manager.run();before=source.read_catalog()['revision']
    original=synchronization.atomic_json
    def fail_pointer(path,value):
        if path.name=='current.json':raise OSError('Disk write failed')
        return original(path,value)
    monkeypatch.setattr(synchronization,'atomic_json',fail_pointer)
    manager.run()
    assert manager.status()['status']=='error' and len(received)==1
    assert source.read_catalog()['revision']==before
    assert json.loads((manager.folder/'current.json').read_text())['revision']==before
    assert len(list((manager.folder/'revisions').iterdir()))==1


def test_publication_rejection_rolls_back_persisted_pointer(rig):
    manager,_=rig;manager.run();before=source.read_catalog()['revision']
    def reject(*args):raise ValueError('Model capacity reached')
    manager.publish=reject;manager.run()
    assert manager.status()['status']=='error'
    assert source.read_catalog()['revision']==before
    assert json.loads((manager.folder/'current.json').read_text())['revision']==before
    assert len(list((manager.folder/'revisions').iterdir()))==1


def test_restart_resumes_schedule_and_shutdown_prevents_publication(rig):
    from datetime import datetime,timedelta,timezone
    manager,received=rig;manager.run()
    manager.save(next_check=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat())
    restored=Synchronizer(manager.folder,manager.publish,enabled=True)
    assert 7100<restored.seconds_until_check()<=7200
    assert Synchronizer(manager.folder,manager.publish).status()['next_check'] is None
    before=source.read_catalog()['revision'];manager.stop_event.set();manager.run()
    assert source.read_catalog()['revision']==before and len(received)==1


def test_sync_permissions_status_and_configuration(tmp_path,monkeypatch):
    with pytest.raises(ValueError):Synchronizer(tmp_path,lambda *a:None,interval=1)
    with pytest.raises(ValueError):Synchronizer(tmp_path,lambda *a:None,enabled=True,readonly=True)
    monkeypatch.setattr(api,'DATA',tmp_path/'uncreated')
    monkeypatch.setattr(api,'SETTINGS',replace(api.SETTINGS,mode='readonly',workers=2))
    with TestClient(api.app) as client:
        assert client.get('/api/sync/status').json()['can_run'] is False
        assert client.post('/api/sync/run').status_code==403
        assert not api.DATA.exists()


def test_sync_trigger_deduplicates_requests_without_network(tmp_path):
    manager=Synchronizer(tmp_path,lambda *a:None)
    assert manager.trigger() and not manager.trigger()
    manager.wake.clear();manager.state['status']='running'
    assert not manager.trigger()


def test_public_raw_argo_conversion_retains_qc_and_never_uses_adjusted_fallback():
    raw=dict(pres=100,temp=28,psal=35,depth=99,qc=dict(pres=1,temp=4,psal=1))
    packet=dict(source_url='https://erddap.incois.gov.in',source_sha256='a'*64,retrieved_at='2026-09-08T00:00:00Z',profiles=[dict(id='test',time='2025-01-01T00:00:00Z',longitude=85,latitude=14,time_qc=1,source_metadata={},levels=[dict(raw=raw,adjusted={})])])
    p=public_profiles(packet)[0]
    t=next(r for r in p['samples'] if r['variable']=='temperature')
    assert t['qc']==4 and t['value']<28 and not t['adjusted']
    assert 'Position QC' in p['warning']
    raw['temp']=None
    assert next(r for r in public_profiles(packet)[0]['samples'] if r['variable']=='temperature')['value'] is None


def test_status_disk_failure_is_visible_and_does_not_escape_scheduler(tmp_path,monkeypatch):
    manager=Synchronizer(tmp_path,lambda *a:None,enabled=True)
    def fail():
        manager.stop_event.set()
        raise OSError('Disk full')
    monkeypatch.setattr(manager,'run',fail)
    manager.loop()
    assert manager.status()['status']=='error' and 'Disk full' in manager.status()['error']
    assert manager.status()['next_check']
