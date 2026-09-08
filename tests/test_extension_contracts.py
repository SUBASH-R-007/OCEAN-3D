import hashlib
import io
import json
import sys
import types
import numpy as np
import pytest
import xarray as xr
from fastapi.testclient import TestClient
from backend import api
from backend.plugins import (VARIABLES,MODEL_ADAPTERS,SENSORS,PRODUCTS,EXTENSIONS,ADAPTER_METADATA,
    load_extension_plugins,registry_snapshot,restore_registries,register_variable,register_sensor,register_model_adapter)
from backend.ingestion import prepare_import,detect_adapter
from scripts.extension_examples import write_examples


@pytest.fixture
def files(tmp_path): return write_examples(tmp_path/'examples')


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'DATA',tmp_path/'imports')
    monkeypatch.setenv('OCEAN_EXTENSION_MODULES','backend.extensions.example_product')
    with TestClient(api.app) as c: yield c


def test_sensor_contracts_retain_times_units_qc_and_geometry(client,files):
    inventory=client.get('/api/extensions').json()
    assert len(inventory['plugins'])==3
    assert {s['id'] for s in inventory['sensors']}=={'mooring','adcp','hf-radar'}
    for name,kind,geometry,count in [('mooring','mooring-csv','time-series',1),('adcp','adcp-csv','profile',3),('hf-radar','hf-radar-csv','surface-current',1)]:
        path=files/f'synthetic-{name}.csv'
        assert detect_adapter(path)==kind
        model,profiles,report=prepare_import(path,'auto','test','fixture')
        assert model is None and len(profiles)==count and report['category']=='observations'
        assert all(p['geometry']==geometry and not p.get('trajectory_id') and not p.get('path') for p in profiles)
        assert report['adapter_contract']=={'id':'ocean-sensors','version':'1.0.0'}
        if name=='mooring':
            assert [r['value'] for r in profiles[0]['samples']]==[28,27.5,27.2]
            assert profiles[0]['time_range']==['2025-09-03T00:00:00Z','2025-09-03T12:00:00Z']
        else:
            assert max(r['value'] for p in profiles for r in p['samples'] if r['variable']=='u')==pytest.approx(.18 if name=='adcp' else .2)
            assert any(r['qc']==4 for p in profiles for r in p['samples'])
    # Read-only scientific comparison retains each mooring sample's timestamp.
    response=client.post('/api/import',files={'file':('station.csv',(files/'synthetic-mooring.csv').read_bytes())})
    assert response.status_code==201,response.text
    profile=next(p for p in api.PROFILES.values() if p.get('sensor_id')=='mooring')
    result=client.get('/api/profiles/'+profile['id'],params={'model':'demo-bob','variable':'temperature'}).json()
    assert result['metrics']['count']==3
    expected=api.MODELS['demo-bob'].sample('temperature',85,14,50,['2025-09-03T00:00:00','2025-09-03T06:00:00','2025-09-03T12:00:00'])
    np.testing.assert_allclose([p['model'] for p in result['pairs']],expected)


@pytest.mark.parametrize('name,old,new,reason',[
    ('hf-radar','2025-09-03T00:00:00Z,0','2025-09-03T00:00:00Z,10','surface depth'),
    ('adcp',',v,',',u,','Duplicate'),
    ('mooring','2025-09-03T06:00:00Z,50','2025-09-03T06:00:00Z,60','fixed depth'),
    ('mooring','85,14,2025-09-03T06','86,14,2025-09-03T06','fixed geographic'),
])
def test_sensor_misinterpretations_reject(client,files,name,old,new,reason):
    path=files/f'synthetic-{name}.csv'
    text=path.read_text().replace(old,new)
    path.write_text(text)
    with pytest.raises(ValueError,match=reason): prepare_import(path,'auto','bad','bad')


def test_derived_product_preview_import_export_and_restart_contract(client,files):
    path=files/'synthetic-ml-output.nc';payload=path.read_bytes()
    preview=client.post('/api/import/inspect',files={'file':(path.name,payload)})
    assert preview.status_code==200,preview.text
    report=preview.json();assert report['category']=='model' and report['kind']=='derived-cf'
    assert report['product']['kind']=='machine-learning' and not list(api.DATA.glob('*.nc'))
    upload=client.post('/api/import',files={'file':(path.name,payload)},headers={'Idempotency-Key':hashlib.sha256(payload).hexdigest()+':auto'})
    assert upload.status_code==201,upload.text
    identity=upload.json()['id'];model=api.MODELS[identity]
    assert model.provenance['synthetic'] and 'No trained ML model' in model.provenance['product']['lineage']['validation']
    frame=client.get('/api/volume',params={'model':identity,'variable':'ml_temperature_anomaly','resolution':8}).json()
    assert frame['provenance']['product']['version']=='1.0.0'
    exported=client.get('/api/export/subset.nc',params={'model':identity,'variable':'ml_temperature_anomaly','index':1})
    with xr.open_dataset(io.BytesIO(exported.content),engine='scipy') as ds, xr.open_dataset(path) as source:
        np.testing.assert_allclose(ds.ml_temperature_anomaly,source.ml_temperature_anomaly.isel(time=slice(1,2)),equal_nan=True)
        assert 'standard_name' not in ds.ml_temperature_anomaly.attrs
        assert json.loads(ds.attrs['ocean3d_lineage'])==model.provenance['product']['lineage']
    manifest=json.loads((api.DATA/(identity+'.json')).read_text())
    api.MODELS.pop(identity).close()
    api.register(api.DATA/manifest['file'],manifest['kind'],identity,manifest['title'],manifest['sha256'],manifest['adapter_contract'])
    assert api.MODELS[identity].provenance['product']==report['product']
    with pytest.raises(ValueError,match='adapter version'):
        api.register(path,'derived-cf','new',expected_contract={'id':'derived-products','version':'different'})
    assert client.post('/api/import?kind=model',files={'file':(path.name,payload)}).status_code==422


@pytest.mark.parametrize('change',[ 'version','lineage','artifact','outputs','standard' ])
def test_derived_metadata_cannot_silently_disappear(client,files,change):
    path=files/'synthetic-ml-output.nc'
    with xr.open_dataset(path) as source: ds=source.load()
    if change=='version': ds.attrs['ocean3d_product_version']='2'
    if change=='lineage': ds.attrs['ocean3d_lineage']='{}'
    if change=='artifact':
        lineage=json.loads(ds.attrs['ocean3d_lineage']);lineage['artifact_sha256']='not a hash';ds.attrs['ocean3d_lineage']=json.dumps(lineage)
    if change=='outputs': ds=ds.rename({'ml_temperature_anomaly':'unregistered_field'})
    if change=='standard': ds.ml_temperature_anomaly.attrs['standard_name']='sea_water_temperature'
    bad=files/'bad.nc';ds.to_netcdf(bad,engine='scipy')
    response=client.post('/api/import',files={'file':('bad.nc',bad.read_bytes())})
    assert response.status_code==422,response.text
    assert not list(api.DATA.glob('*.nc')) and not list(api.DATA.glob('*.upload'))


def test_pack_registration_is_atomic_and_rejects_unknown_api(monkeypatch):
    before=registry_snapshot()
    module=types.ModuleType('fixture_extension')
    module.PLUGIN={'api_version':1,'id':'broken','version':'1','label':'broken pack'}
    def register():
        register_sensor(dict(id='test-station',label='Test station',geometry='time-series',description='fixture'))
        register_model_adapter('custom-model',lambda path:None,label='fixture',detector=lambda meta:False)
        raise ValueError('broken pack')
    module.register=register;monkeypatch.setitem(sys.modules,'fixture_extension',module)
    with pytest.raises(ValueError,match='broken pack'):load_extension_plugins('fixture_extension')
    assert 'test-station' not in SENSORS and 'custom-model' not in MODEL_ADAPTERS and 'custom-model' not in ADAPTER_METADATA
    module.PLUGIN['api_version']=2
    with pytest.raises(ValueError,match='version 1'):load_extension_plugins('fixture_extension')
    for registry,snapshot in before: assert registry==snapshot


def test_registered_model_adapter_runs_through_core_normalization(client,files):
    def parser(path):
        ds=xr.open_dataset(path);ds.attrs.pop('ocean3d_product_id',None)
        return ds,{'source':'Trusted custom model reader'}
    register_model_adapter('custom-model',parser,label='Custom model',detector=lambda meta:False)
    model,_,report=prepare_import(files/'synthetic-ml-output.nc','custom-model','custom','custom')
    try:
        assert report['category']=='model' and model.ds.ml_temperature_anomaly.dims==('time','depth','latitude','longitude')
    finally:model.close()


def test_series_coverage_uses_actual_sample_times_not_start_or_span():
    from backend.demo import build_demo
    from backend.analysis import coverage
    model,_=build_demo()
    profile={'longitude':85,'latitude':14,'time':'2025-01-01T00:00:00Z','samples':[
        {'variable':'temperature','value':28,'depth':50,'qc':1,'time':'2025-09-03T00:00:00Z'}]}
    try:
        assert coverage(model,[profile],'temperature',2)['eligible_profiles']==1
        profile['samples'][0]['time']='2025-09-06T00:00:00Z'
        assert coverage(model,[profile],'temperature',2)['eligible_profiles']==0
    finally:model.close()


def test_variable_contract_recognizes_its_canonical_name_and_unit():
    from backend.demo import build_demo
    from backend.science import normalize
    snapshot=registry_snapshot()
    model=None
    try:
        register_variable(dict(id='derived_signal',label='Synthetic signal',unit='°C',
            standard=None,aliases=['source_signal'],range=[-2,2],
            unit_aliases=['degc'],canonical_unit='degree_Celsius'))
        model,_=build_demo()
        raw=model.ds[['temperature']].rename({'temperature':'derived_signal'})
        raw.derived_signal.attrs=dict(units='degree_Celsius',long_name='Synthetic signal')
        normalized=normalize(raw)
        assert set(normalized.data_vars)=={'derived_signal'}
        assert 'standard_name' not in normalized.derived_signal.attrs
        np.testing.assert_allclose(normalized.derived_signal,raw.derived_signal,equal_nan=True)
    finally:
        if model: model.close()
        restore_registries(snapshot)


def test_empty_product_identity_cannot_bypass_validation(client,files):
    path=files/'synthetic-ml-output.nc'
    with xr.open_dataset(path) as source: ds=source.load()
    ds.attrs['ocean3d_product_id']=''
    payload=bytes(ds.to_netcdf(engine='scipy'))
    for kind in ('auto','model'):
        response=client.post('/api/import?kind='+kind,files={'file':('invalid.nc',payload)})
        assert response.status_code==422,response.text
    assert not list(api.DATA.glob('*.nc'))
