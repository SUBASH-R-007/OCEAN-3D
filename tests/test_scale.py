import json
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pytest
import xarray as xr
from dask.callbacks import Callback
from fastapi.testclient import TestClient
from backend import api
from backend.archive import load_archives
from backend.science import Model, normalize, file_hash
from backend.transport import ByteCache, encode_volume


def test_oversized_storage_chunks_are_rejected_before_scientific_reads(tmp_path):
    from netCDF4 import Dataset
    from backend.science import open_bounded_model
    path=tmp_path/'large-chunk.nc'
    with Dataset(path,'w') as ds:
        for name,size in [('time',4),('depth',64),('latitude',512),('longitude',512)]: ds.createDimension(name,size)
        ds.createVariable('thetao','f4',('time','depth','latitude','longitude'),chunksizes=(4,64,512,512),zlib=True)
    with pytest.raises(ValueError,match='32 MiB'): open_bounded_model(path)


def test_ogc_catalogs_reject_excessive_metadata_before_allocation():
    from types import SimpleNamespace
    from backend.ogc import wms_capabilities, wcs_request
    model=SimpleNamespace(ds=SimpleNamespace(sizes={'time':100000,'depth':5000},data_vars={'temperature':None,'salinity':None}))
    with pytest.raises(ValueError,match='metadata'): wms_capabilities({'large':model},'http://example.invalid/wms')
    with pytest.raises(ValueError,match='4096'): wcs_request({'large':model},{'REQUEST':'GetCapabilities'},'http://example.invalid/wcs')


def source_dataset(offset=0):
    dates=np.array(['2025-01-01','2025-01-02'],dtype='datetime64[ns]')+np.timedelta64(offset,'D')
    t,z,y,x=np.meshgrid([offset,offset+1],[0,100,200],[10,11,12],[80,81,82],indexing='ij')
    values=(t+z*.01+y+x).astype('float32'); values[:,:,0,0]=np.nan
    return xr.Dataset({'thetao':(('time','depth','latitude','longitude'),values,{'units':'degree_Celsius','standard_name':'sea_water_potential_temperature'})},coords={'time':dates,'depth':('depth',[0,100,200],{'units':'m','positive':'down'}),'latitude':[10,11,12],'longitude':[80,81,82]},attrs={'synthetic':'true'})


def manifest(tmp_path, offsets=(0,2)):
    files=[]
    for i,offset in enumerate(offsets):
        path=tmp_path/f'part-{i}.nc';source_dataset(offset).to_netcdf(path)
        files.append({'path':path.name,'sha256':file_hash(path)})
    value={'version':1,'archives':[{'id':'archive-test','title':'Synthetic archive','files':files}]}
    path=tmp_path/'archive.json';path.write_text(json.dumps(value))
    return path,value


def test_archive_is_lazy_exact_and_bounded(tmp_path):
    path,_=manifest(tmp_path)
    tasks=[]
    with Callback(posttask=lambda key,*args: tasks.append(str(key))):
        models=load_archives(path)
    assert tasks==[], 'Registration must not compute scientific arrays.'
    model=models[0]
    try:
        assert model.ds.sizes['time']==4 and model.ds.temperature.chunks[0]==(1,1,1,1)
        assert model.catalog()['provenance']['storage']=='lazy-netcdf-time-archive'
        assert model.sample('temperature',81,11,50,'2025-01-02T12:00')[0]==pytest.approx(94)
        frame=model.volume('temperature',3,8,150,[80.5,10.5,81.5,11.5])
        assert frame['bbox']==[80.5,10.5,81.5,11.5]
        assert frame['axes']['depth'][-1]==150
        z,y,x=np.meshgrid(frame['axes']['depth'],frame['axes']['latitude'],frame['axes']['longitude'],indexing='ij')
        expected=3+z*.01+y+x
        values=np.array(frame['values'],dtype=float).reshape(z.shape)
        assert np.isnan(values[:,0,0]).all()
        assert np.allclose(values[np.isfinite(values)],expected[np.isfinite(values)],atol=1e-5)
    finally: model.close()


@pytest.mark.parametrize('failure',['checksum','overlap','spatial','escape','identity'])
def test_archive_rejects_incompatible_sources(tmp_path,failure):
    path,doc=manifest(tmp_path, (0,0) if failure=='overlap' else (0,2))
    entry=doc['archives'][0]
    if failure=='checksum': entry['files'][0]['sha256']='0'*64
    if failure=='spatial':
        p=tmp_path/'part-1.nc';source_dataset(2).assign_coords(latitude=[10,11,13]).to_netcdf(p)
        entry['files'][1]['sha256']=file_hash(p)
    if failure=='escape':
        outer=tmp_path.parent/'outside.nc';source_dataset().to_netcdf(outer)
        entry['files'][0]={'path':'../outside.nc','sha256':file_hash(outer)}
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError): load_archives(path, ['archive-test'] if failure=='identity' else [])


def test_region_mask_and_parameter_contract():
    model=Model('x',normalize(source_dataset()),{'title':'test'})
    for bbox in ([82,10,80,12],[80,10,float('nan'),12],[79,10,82,12],[80,10,81]):
        with pytest.raises(ValueError): model.volume('temperature',0,8,bbox=bbox)
    for resolution in (0,65,8.5):
        with pytest.raises(ValueError): model.volume('temperature',0,resolution)
    volume=model.volume('temperature',0,8)
    encoded=encode_volume(volume);length=struct.unpack('<I',encoded[4:8])[0]
    meta=json.loads(encoded[8:8+length]);values=np.frombuffer(encoded,dtype='<f4',offset=8+length)
    assert meta['encoding']['missing']=='NaN'
    assert np.allclose(values,np.asarray(volume['values'],float),equal_nan=True)
    assert np.isnan(values).sum()==3


def test_byte_cache_evicts_by_size_and_recency():
    cache=ByteCache(limit=10)
    cache.put('a',b'1234');cache.put('b',b'5678');assert cache.get('a')==b'1234'
    cache.put('c',b'12345');assert cache.get('b') is None and cache.stats()['payload_bytes']==9
    cache.put('a',b'x');assert cache.stats()['payload_bytes']==6
    cache.put('too-large',b'x'*11);assert cache.get('too-large') is None
    with pytest.raises(TypeError): cache.put('mutable',bytearray(1))
    cache.clear();assert cache.stats()['payload_bytes']==0


def test_binary_api_region_cache_and_admission(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'DATA',tmp_path)
    with TestClient(api.app) as client:
        params={'resolution':8,'bbox':'84,12,87,16','maximum_depth':200}
        binary=client.get('/api/volume.bin',params=params)
        regular=client.get('/api/volume',params=params)
        assert binary.status_code==regular.status_code==200
        length=struct.unpack('<I',binary.content[4:8])[0]
        values=np.frombuffer(binary.content,dtype='<f4',offset=8+length)
        assert np.allclose(values,np.array(regular.json()['values'],float),equal_nan=True)
        before=client.get('/api/runtime').json()['frames']['hits']
        assert client.get('/api/volume.bin',params=params).content==binary.content
        assert client.get('/api/runtime').json()['frames']['hits']>before
        assert client.get('/api/volume.bin?bbox=bad').status_code==422
        for _ in range(api.MAX_ACTIVE): assert api.WORK_SLOTS.acquire(False)
        try:
            overloaded=client.get('/api/volume.bin')
            assert overloaded.status_code==503 and overloaded.headers['retry-after']=='2'
            assert client.get('/api/health').status_code==200
        finally:
            for _ in range(api.MAX_ACTIVE): api.WORK_SLOTS.release()


def test_import_does_not_block_event_loop(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'DATA',tmp_path)
    entered,released=threading.Event(),threading.Event()
    def delayed(path):
        entered.set()
        assert released.wait(5)
        return [dict(id='CAST',instrument='CTD',latitude=14,longitude=85,
                     time='2025-01-01T00:00:00Z',data_mode='R',source='Synthetic concurrency fixture',synthetic=True,
                     samples=[dict(depth=10,variable='temperature',value=28,qc=1,adjusted=False,error=None)])]
    monkeypatch.setitem(api.ADAPTERS,'slow-test',delayed)
    with TestClient(api.app) as client, ThreadPoolExecutor(1) as pool:
        upload=pool.submit(lambda:client.post('/api/import?kind=slow-test',files={'file':('test.txt',b'fixture')}))
        assert entered.wait(2)
        try:
            start=time.monotonic()
            assert client.get('/api/health').status_code==200
            assert time.monotonic()-start<1
        finally: released.set()
        assert upload.result(timeout=5).status_code==201
