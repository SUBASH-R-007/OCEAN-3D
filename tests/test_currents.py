"""Scientific verification of the source-backed depth-resolved current case."""
import io
import json
import numpy as np
import pytest
import xarray as xr
from backend.hycom import convert_currents, load_currents, FOLDER, MODEL_ID
from backend.exports import subset_netcdf


def fixture_sources():
    dims=('time','depth','lat','lon')
    coords=dict(time=np.array(['2023-09-01T12:00'],dtype='datetime64[ns]'),
        depth=('depth',[0.,100.],dict(units='m',positive='down')),lat=[-1.,1.],lon=[70.,72.])
    uv=xr.Dataset({
        'water_u':(dims,np.array([[[[1.,0.],[-1.,np.nan]],[[.1,.2],[.3,.4]]]]),dict(units='m/s',standard_name='eastward_sea_water_velocity')),
        'water_v':(dims,np.ones((1,2,2,2))*.2,dict(units='m/s',standard_name='northward_sea_water_velocity')),
    },coords=coords)
    ts=xr.Dataset({
        'water_temp':(dims,np.ones((1,2,2,2))*20,dict(units='degC',standard_name='sea_water_temperature')),
        'salinity':(dims,np.ones((1,2,2,2))*35,dict(units='psu',standard_name='sea_water_salinity')),
    },coords=coords)
    return uv,ts


def test_source_component_signs_and_missing_cells_survive_conversion():
    uv,ts=fixture_sources();ds=convert_currents(uv,ts)
    np.testing.assert_array_equal(ds.u.values,uv.water_u.values.astype('float32'))
    np.testing.assert_array_equal(ds.v.values,uv.water_v.values.astype('float32'))
    assert ds.u.attrs['standard_name']=='eastward_sea_water_velocity'
    assert 'w' not in ds


def test_currents_reject_staggered_grids_rotated_vectors_and_wrong_units():
    uv,ts=fixture_sources()
    with pytest.raises(ValueError,match='coordinates differ'):
        convert_currents(uv,ts.assign_coords(lat=[-1.,1.01]))
    uv.water_u.attrs['standard_name']='sea_water_x_velocity'
    with pytest.raises(ValueError,match='definition or units'):convert_currents(uv,ts)


def test_matching_valid_times_do_not_hide_different_forecast_initializations():
    uv,ts=fixture_sources()
    attrs=dict(standard_name='forecast_reference_time')
    uv['time_run']=('time',np.array(['2023-09-01T12:00'],dtype='datetime64[ns]'),attrs)
    ts['time_run']=('time',np.array(['2023-08-31T12:00'],dtype='datetime64[ns]'),attrs)
    with pytest.raises(ValueError,match='initialization times differ'):convert_currents(uv,ts)
    uv,ts=fixture_sources();uv.water_v.attrs['units']='unknown'
    with pytest.raises(ValueError,match='definition or units'):convert_currents(uv,ts)


def test_real_current_archive_source_and_full_depth_exports():
    model=load_currents()
    assert model and model.id==MODEL_ID and not model.provenance['synthetic']
    assert model.ds.sizes['depth']==40 and model.ds.sizes['time']==3
    assert model.ds.depth.values[[0,-1]].tolist()==[0,5000]
    assert model.provenance['vertical_velocity_available'] is False
    assert model.provenance['forecast_lead_hours']==[24,27,30]
    with xr.open_dataset(FOLDER/'uv3z-source.nc') as raw:
        np.testing.assert_array_equal(model.ds.u.values,raw.water_u.values.astype('float32'))
        np.testing.assert_array_equal(model.ds.v.values,raw.water_v.values.astype('float32'))
        assert np.isnan(raw.water_u.values).any()
    assert float(np.abs(model.ds.u.isel(time=2)-model.ds.u.isel(time=0)).max()) > .01
    assert np.isfinite(model.ds.u.isel(depth=-1)).any()
    content=subset_netcdf(model,'u',1)
    with xr.open_dataset(io.BytesIO(content)) as exported:
        np.testing.assert_array_equal(exported.u.values,model.ds.u.isel(time=slice(1,2)).values)
        assert exported.u.attrs['units']=='m s-1'
    for index in range(3):
        u=model.volume('u',index,resolution=16);v=model.volume('v',index,resolution=16)
        assert u['axes']==v['axes'] and u['time']==v['time']
        assert u['axes']['depth'][-1]==5000
        assert u['valid_cells'] and v['valid_cells']
