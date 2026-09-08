import hashlib
import json
import csv
import io
from pathlib import Path
import numpy as np
import pytest
import xarray as xr
from fastapi.testclient import TestClient
from backend import api
from backend.observations import ADAPTERS, parse_csv
from backend.ingestion import detect_adapter, prepare_import
from backend.plugins import register_observation_adapter, unregister_adapters, register_variable
from backend.science import VARIABLES, normalize
from backend.demo import build_demo

HEADER=['profile_id','instrument','longitude','latitude','time','depth','variable','value','unit','qc','synthetic']
ROW=['P','CTD','85','14','2025-09-03T12:00:00Z','10','temperature','300','K','1','true']


def table(tmp_path, header=HEADER, rows=None, delimiter=','):
    target=tmp_path/'table.txt'
    text=io.StringIO(); writer=csv.writer(text,delimiter=delimiter)
    writer.writerow(header);writer.writerows(rows or [ROW])
    target.write_text('\ufeff# Mission export\n'+text.getvalue(),encoding='utf-8')
    return target


@pytest.mark.parametrize('delimiter',[',','\t',';','|',' '])
def test_delimited_dialects_units_and_native_values(tmp_path,delimiter):
    p=parse_csv(table(tmp_path,delimiter=delimiter))[0]
    row=p['samples'][0]
    assert row['value']==pytest.approx(26.85)
    assert row['source_value']==300 and row['source_unit']=='K'
    assert row['time']=='2025-09-03T12:00:00Z' and row['qc']==1
    assert row['source_row']==2 and p['synthetic']


def test_wide_aliases_qc_and_moving_samples(tmp_path):
    header=['profile_id','instrument','lon','lat','timestamp','depth','depth_unit','thetao','thetao_unit','thetao_qc','uo','uo_unit','uo_error','synthetic']
    rows=[['MOVE','Glider','85','14','2025-09-03T17:30:00+05:30','0.01','km','300','K','2','20','cm/s','2','true'],['MOVE','Glider','85.1','14.1','2025-09-03T12:05:00Z','0.1','km','NA','K','9','-15','cm/s','1','true']]
    p=parse_csv(table(tmp_path,header,rows))[0]
    t=[r for r in p['samples'] if r['variable']=='temperature']
    u=[r for r in p['samples'] if r['variable']=='u']
    assert [r['value'] for r in u]==[.2,-.15] and u[0]['error']==.02
    assert u[0]['qc']==0 and t[1]['value'] is None
    assert t[0]['depth']==10 and t[1]['longitude']==85.1
    assert p['time_range']==['2025-09-03T12:00:00Z','2025-09-03T12:05:00Z']
    assert len(p['path'])==2 and 'Missing QC' in p['import_warnings'][0]


@pytest.mark.parametrize(('column','value','message'),[('unit','fahrenheit','unsupported unit'),('qc','1.5','integer'),('depth','-5','positive down'),('longitude','200','coordinates'),('time','2025-09-03T12:00:00','UTC offset'),('value','inf','finite'),('synthetic','yes','true or false'),('variable','unknown','Unknown or ambiguous')])
def test_bad_text_reports_record_and_rejects(tmp_path,column,value,message):
    row=ROW.copy();row[HEADER.index(column)]=value
    with pytest.raises(ValueError,match='Table record 2:.*'+message):parse_csv(table(tmp_path,rows=[row]))


def test_quoted_multiline_headers_and_schema_validation(tmp_path):
    row=ROW.copy();row[1]='Research, vessel\nCTD'
    assert parse_csv(table(tmp_path,rows=[row]))[0]['instrument']==row[1]
    with pytest.raises(ValueError,match='unique'):parse_csv(table(tmp_path,HEADER+['lon'],[ROW+['85']]))
    with pytest.raises(ValueError,match='Expected .* fields'):parse_csv(table(tmp_path,rows=[ROW[:-1]]))
    with pytest.raises(ValueError,match='incompatible standard_name'):parse_csv(table(tmp_path,HEADER+['standard_name'],[ROW+['sea_water_temperature']]))


def test_registered_variable_text_and_netcdf_contract(tmp_path):
    definition=json.loads((api.ROOT/'config/variables.example.json').read_text())[0]
    try:
        register_variable(definition)
        row=ROW.copy();row[6:9]=['oxygen','210','mmol m-3']
        assert parse_csv(table(tmp_path,rows=[row]))[0]['samples'][0]['value']==210
        row[8]=''
        with pytest.raises(ValueError,match='explicit canonical unit'):parse_csv(table(tmp_path,rows=[row]))
        model,_=build_demo();ds=model.ds.copy();ds['o2']=ds.temperature*0+210;ds.o2.attrs={'standard_name':definition['standard'],'units':'mmol m-3'}
        assert 'oxygen' in normalize(ds)
    finally: VARIABLES.pop('oxygen',None)


def test_auxiliary_cf_model_axes_packing_and_units(tmp_path):
    model,_=build_demo();ds=model.ds.rename_dims({'longitude':'x','latitude':'y','depth':'z','time':'t'})
    ds.longitude.attrs={'standard_name':'longitude','units':'degrees_east'}
    ds.latitude.attrs={'standard_name':'latitude','units':'degrees_north'}
    source=tmp_path/'axis.nc'
    ds.to_netcdf(source,encoding={'temperature':{'dtype':'int16','scale_factor':.01,'_FillValue':-32768}})
    assert detect_adapter(source)=='model'
    imported,_,report=prepare_import(source,'auto','axes','Axis fixture')
    try:
        assert imported.ds.temperature.dims==('time','depth','latitude','longitude')
        with xr.open_dataset(source) as native:
            np.testing.assert_allclose(imported.ds.temperature.values,native.temperature.values,atol=2e-6,equal_nan=True)
        assert report['shape']['longitude']==ds.sizes['x'] and report['time_steps']==ds.sizes['t']
    finally: imported.close()
    ds.longitude.attrs['units']='m'
    with pytest.raises(ValueError,match='angular degree'):normalize(ds)


def test_real_native_format_detection():
    root=api.ROOT
    for name,expected in [('glider-native-subset.nc','imos-glider'),('ctd-native-subset.nc','cchdo-ctd'),('bgc-incois.nc','argo')]:
        assert detect_adapter(root/'data/instruments'/name)==expected
    assert detect_adapter(root/'web/public/examples/synthetic-glider.nc')=='cf-profile'


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'DATA',tmp_path/'imports')
    # This suite exercises ingestion, not repeated startup of large source collections.
    monkeypatch.setattr(api,'load_reference',lambda:None)
    monkeypatch.setattr(api,'load_incois',lambda:None)
    monkeypatch.setattr(api,'load_currents',lambda:None)
    monkeypatch.setattr('backend.incois_catalog.load_basin_models',lambda:[])
    monkeypatch.setattr('backend.instrument_sources.load_instrument_cases',lambda:[])
    with TestClient(api.app) as c: yield c


def test_preview_commit_idempotence_restore_and_rejection(client,tmp_path):
    payload=table(tmp_path).read_bytes();before=set(api.PROFILES)
    preview=client.post('/api/import/inspect',files={'file':('new.txt',payload)})
    assert preview.status_code==200,preview.text
    report=preview.json();assert report['kind']=='csv' and report['qc']=={'good':1}
    assert set(api.PROFILES)==before and not list(api.DATA.iterdir())
    digest=hashlib.sha256(payload).hexdigest()
    response=client.post('/api/import',files={'file':('../mission.txt',payload)},headers={'Idempotency-Key':digest+':auto'})
    assert response.status_code==201,response.text
    result=response.json();identity=result['id']
    again=client.post('/api/import?kind=csv',files={'file':('mission.txt',payload)},headers={'Idempotency-Key':digest+':csv'})
    assert again.json()['id']==identity and again.json()['duplicate']
    manifest=json.loads((api.DATA/(identity+'.json')).read_text())
    assert manifest['title']=='mission.txt' and manifest['report']['sha256']==digest
    assert (api.DATA/manifest['file']).read_bytes()==payload
    api.PROFILES.pop(identity+':P');api.register(api.DATA/manifest['file'],manifest['kind'],identity,manifest['title'])
    assert identity+':P' in api.PROFILES
    files=set(api.DATA.iterdir());profiles=set(api.PROFILES)
    failed=client.post('/api/import/inspect',files={'file':('bad.txt',b'invalid')})
    assert failed.status_code==422 and set(api.DATA.iterdir())==files and set(api.PROFILES)==profiles
    failed=client.post('/api/import',files={'file':('bad.txt',payload)},headers={'Idempotency-Key':'wrong'})
    assert failed.status_code==422 and set(api.DATA.iterdir())==files
    with pytest.raises(ValueError,match='checksum'):
        api.register(api.DATA/manifest['file'],manifest['kind'],'altered',expected_sha256='0'*64)


def test_custom_netcdf_adapter_registry_preview_and_persistence(client,tmp_path):
    source=tmp_path/'custom.nc';xr.Dataset(attrs={'source_contract':'test-native'}).to_netcdf(source)
    def parser(path):
        with xr.open_dataset(path) as ds: assert ds.attrs['source_contract']=='test-native'
        return [{'id':'CUSTOM','instrument':'Mooring','longitude':85,'latitude':14,'time':'2025-09-03T12:00:00Z','synthetic':True,'samples':[dict(variable='u',depth=10,value=.3,qc=1,adjusted=False,error=None)]}]
    try:
        register_observation_adapter('custom-native',parser,container='netcdf',label='Custom native sensor',detector=lambda meta:meta['attrs'].get('source_contract')=='test-native')
        assert detect_adapter(source)=='custom-native'
        formats=client.get('/api/adapters').json()['formats'];spec=next(f for f in formats if f['id']=='custom-native')
        assert spec['accept']=='.nc,.nc4,.cdf'
        response=client.post('/api/import',files={'file':('native.nc',source.read_bytes())})
        assert response.status_code==201,response.text
        result=response.json();assert result['kind']=='custom-native'
        manifest=json.loads((api.DATA/(result['id']+'.json')).read_text());assert manifest['file'].endswith('.nc')
        register_observation_adapter('ambiguous-native',parser,container='netcdf',detector=lambda meta:meta['attrs'].get('source_contract')=='test-native')
        with pytest.raises(ValueError,match='Ambiguous'):detect_adapter(source)
        assert detect_adapter(source,'custom-native')=='custom-native'
    finally:unregister_adapters(['custom-native','ambiguous-native'])


def test_inbox_receipts_distinguish_adapter_and_failures(tmp_path,monkeypatch):
    import httpx
    from scripts.ingest_inbox import ingest_inbox
    payload=table(tmp_path).read_bytes();source=tmp_path/'mission.txt';source.write_bytes(payload)
    digest=hashlib.sha256(payload).hexdigest();marker=tmp_path/'mission.txt.ready.json'
    calls=[]
    def respond(request):
        calls.append(request)
        return httpx.Response(201,json={'id':'test','sha256':digest,'kind':'csv'})
    client_type=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw:client_type(transport=httpx.MockTransport(respond),**kw))
    marker.write_text(json.dumps({'kind':'auto','sha256':digest}))
    assert ingest_inbox(tmp_path,'http://test')[0]['status']=='imported'
    assert ingest_inbox(tmp_path,'http://test')[0]['status']=='already imported'
    marker.write_text(json.dumps({'kind':'csv','sha256':digest}))
    assert ingest_inbox(tmp_path,'http://test')[0]['status']=='imported' and len(calls)==2
    assert not list(tmp_path.glob('*.pending')) and source.read_bytes()==payload
    marker.write_text(json.dumps({'kind':'csv','sha256':'invalid'}))
    assert ingest_inbox(tmp_path,'http://test')[0]['status']=='error'


def test_adapter_module_registration_rolls_back(monkeypatch):
    import types
    from backend.plugins import load_adapter_plugins,ADAPTER_METADATA
    def register():
        register_observation_adapter('module-test',lambda path:[])
        raise ValueError('Incomplete deployment plugin')
    monkeypatch.setattr('importlib.import_module',lambda name:types.SimpleNamespace(register=register))
    with pytest.raises(ValueError,match='Incomplete'):load_adapter_plugins('test_installed.adapter')
    assert 'module-test' not in ADAPTERS and 'module-test' not in ADAPTER_METADATA
