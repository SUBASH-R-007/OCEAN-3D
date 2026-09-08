import numpy as np
import pytest
import xarray as xr
from backend.science import Model, normalize
from backend.analysis import compare, transect, coverage
from backend.observations import parse_csv, parse_argo

@pytest.fixture
def model():
    # Affine field has a known analytic answer at every interior point, in all four dimensions.
    t,z,y,x=np.meshgrid([0,24],[0,100],[10,12],[80,82],indexing='ij')
    ds=xr.Dataset({'thetao':(('time','depth','latitude','longitude'),(t+z*.1+y*2+x*3).astype(float),{'units':'degree_Celsius','standard_name':'sea_water_potential_temperature'})},coords={'time':np.array(['2025-01-01','2025-01-02'],dtype='datetime64[ns]'),'depth':('depth',[0,100],{'units':'m','positive':'down'}),'latitude':[10,12],'longitude':[80,82]})
    return Model('test',normalize(ds),{'title':'Affine test fixture','synthetic':True})

def test_four_dimensional_interpolation(model):
    assert model.sample('temperature',81,11,50,'2025-01-01T12:00')[0]==pytest.approx(12+5+22+243)

@pytest.mark.parametrize('query',[(79,11,50,'2025-01-01T12:00'),(81,13,50,'2025-01-01T12:00'),(81,11,101,'2025-01-01T12:00'),(81,11,50,'2025-01-03')])
def test_no_extrapolation(model,query):
    assert np.isnan(model.sample('temperature',*query)[0])

def test_missing_corner_propagates(model):
    model.ds.temperature.values[0,0,0,0]=np.nan
    assert np.isnan(model.sample('temperature',81,11,50,'2025-01-01T12:00')[0])

def test_large_temporal_gap_rejected(model):
    assert np.isnan(model.sample('temperature',81,11,50,'2025-01-01T12:00',max_gap_hours=12)[0])
    assert np.isfinite(model.sample('temperature',81,11,50,'2025-01-01',max_gap_hours=12)[0])

def test_sort_negative_depth_kelvin_and_longitude(model):
    ds=model.ds.rename({'temperature':'thetao','longitude':'lon','latitude':'lat'})
    ds=ds.assign_coords(lon=ds.lon+360,depth=-ds.depth)
    ds.depth.attrs={'units':'m','positive':'up'}
    ds.thetao.values+=273.15;ds.thetao.attrs={'units':'K','standard_name':'sea_water_potential_temperature'}
    ds=ds.isel(lat=slice(None,None,-1),time=slice(None,None,-1))
    normalized=normalize(ds)
    assert normalized.longitude.values.tolist()==[80,82]
    assert normalized.depth.values.tolist()==[0,100]
    assert float(normalized.temperature.isel(time=0,depth=0,latitude=0,longitude=0))==pytest.approx(260,abs=1e-4)

def test_ambiguous_temperature_rejected(model):
    model.ds.temperature.attrs['standard_name']='sea_water_temperature'
    with pytest.raises(ValueError,match='not the supported'):normalize(model.ds)

def test_bad_axis_rejected(model):
    with pytest.raises(ValueError,match='unique'):normalize(model.ds.assign_coords(longitude=[80,80]))
    model.ds.depth.attrs['units']='dbar'
    with pytest.raises(ValueError,match='metres'):normalize(model.ds)

def profile():
    return dict(id='TEST',latitude=11,longitude=81,time='2025-01-01T12:00:00Z',samples=[dict(depth=z,value=v,qc=q,variable='temperature',adjusted=True,error=.01) for z,v,q in [(0,276,1),(50,280,2),(75,999,4),(200,100,1)]])

def test_qc_metrics_and_unmatched(model):
    strict=compare(model,profile(),'temperature')
    assert strict['metrics']==dict(count=1,total=4,qc_excluded=2,unmatched=1,bias=1.,rmse=1.,mae=1.)
    relaxed=compare(model,profile(),'temperature','lenient')
    assert relaxed['metrics']['count']==2
    assert relaxed['metrics']['bias']==pytest.approx(1.5)
    assert relaxed['metrics']['rmse']==pytest.approx(np.sqrt(2.5))

def test_empty_matches_are_null_not_zero(model):
    p=profile();p['time']='2026-01-01T00:00:00Z'
    m=compare(model,p,'temperature')['metrics']
    assert m['count']==0 and m['rmse'] is None

def test_volume_order_and_bounds(model):
    volume=model.volume('temperature',0,8)
    assert volume['dimensions']==[2,2,2]
    assert volume['values']==[260.,266.,264.,270.,270.,276.,274.,280.]
    with pytest.raises(ValueError): model.volume('temperature',20)

def test_transect_shape_and_outside_support(model):
    result=transect(model,'temperature',0,[79,11],[83,11])
    assert len(result['values'])==32 and len(result['values'][0])==48
    assert result['values'][0][0] is None and result['values'][0][-1] is None
    assert result['values'][0][24] is not None

def test_coverage_no_data_is_not_zero_distance(model):
    result=coverage(model,[],'temperature',0)
    assert result['eligible_profiles']==0 and result['priority']==[]
    assert all(c['distance_km'] is None for c in result['cells'])

def test_delimited_adapter_validates_position_and_empty(tmp_path):
    path=tmp_path/'profiles.csv';header='profile_id,instrument,longitude,latitude,time,depth,variable,value,qc\n'
    path.write_text(header+'P,CTD,81,11,2025-01-01T00:00:00Z,10,temperature,20,1\n')
    assert parse_csv(path)[0]['samples'][0]['value']==20
    path.write_text(header+'P,CTD,81,91,2025-01-01T00:00:00Z,10,temperature,20,1\n')
    with pytest.raises(ValueError,match='coordinates'):parse_csv(path)
    path.write_text(header)
    with pytest.raises(ValueError,match='No observation'):parse_csv(path)

def test_argo_adjusted_qc_and_teos(tmp_path):
    import gsw
    data={n:(('N_PROF','N_LEVELS'),[a]) for n,a in {'PRES':[10.,100.],'TEMP':[30.,25.],'PSAL':[35.,35.], 'PRES_ADJUSTED':[10.,100.], 'TEMP_ADJUSTED':[29.,24.], 'PSAL_ADJUSTED':[34.,34.]}.items()}
    for n in ['PRES','TEMP','PSAL','PRES_ADJUSTED','TEMP_ADJUSTED','PSAL_ADJUSTED']:data[n+'_QC']=(('N_PROF','N_LEVELS'),np.array([[b'1',b'4' if n=='TEMP_ADJUSTED' else b'1']],dtype='S1'))
    data.update(LONGITUDE=('N_PROF',[85.]),LATITUDE=('N_PROF',[14.]),JULD=('N_PROF',np.array(['2025-01-01'],dtype='datetime64[ns]')),DATA_MODE=('N_PROF',[b'D']),PLATFORM_NUMBER=('N_PROF',[b'2900001']),CYCLE_NUMBER=('N_PROF',[5]))
    path=tmp_path/'argo.nc';xr.Dataset(data).to_netcdf(path)
    p=parse_argo(path)[0];temp=[r for r in p['samples'] if r['variable']=='temperature']
    assert temp[0]['adjusted'] and temp[1]['qc']==4
    assert temp[0]['depth']==pytest.approx(-gsw.z_from_p(10,14),abs=.001)
    assert temp[0]['value']==pytest.approx(gsw.pt0_from_t(gsw.SA_from_SP(34,10,85,14),29,10))
