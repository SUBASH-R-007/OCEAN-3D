import io
import json
import jsonschema
from pathlib import Path
import numpy as np
import pytest
import xarray as xr
from backend.reference import load_reference
from backend.observations import parse_argo
from backend.analysis import compare
from backend.diagnostics import diagnose_observation, column_diagnostics
from backend.exports import subset_netcdf, coverage_json


@pytest.fixture
def case():
    result=load_reference()
    assert result is not None, 'Run python -m scripts.bootstrap_reference to install the documented real case.'
    return result


def test_real_pair_checksums_qc_units_and_collocation(case):
    model,profiles=case
    good=profiles[0]
    assert good['sha256']=='09ffebf6f46372b67c76667732627f7b1eb210ede328975cae6c68a45a3f0aaf'
    assert not model.provenance['synthetic'] and good['data_mode']=='D'
    assert good['time']=='2023-09-01T15:49:17.001680Z'
    result=compare(model,good,'temperature')
    assert result['metrics']['count']==1001
    assert result['metrics']['rmse']==pytest.approx(.655267028998,abs=1e-7)
    assert result['metrics']['bias']==pytest.approx(.105452344574,abs=1e-7)
    assert all(p['adjusted'] for p in result['pairs'])


def test_rejected_salinity_cannot_be_replaced_by_raw(case):
    model,profiles=case
    bad=profiles[1]
    result=compare(model,bad,'temperature')
    assert result['metrics']['qc_excluded']==511
    assert result['metrics']['count']==0 and result['metrics']['rmse'] is None
    assert diagnose_observation(bad)['density_mld']['status']=='reference_unavailable'


def test_delayed_mode_missing_adjusted_fields_never_falls_back(tmp_path):
    source=Path(__file__).resolve().parents[1]/'data/reference/D5904729_274.nc'
    with xr.open_dataset(source) as ds:
        modified=ds.drop_vars(['PSAL_ADJUSTED','PSAL_ADJUSTED_QC','PSAL_ADJUSTED_ERROR']).load()
    path=tmp_path/'missing-adjusted.nc';modified.to_netcdf(path)
    profile=parse_argo(path)[0]
    assert all(row['value'] is None for row in profile['samples'])


def test_bgc_parameter_mode_overrides_profile_mode_and_requires_units(tmp_path):
    source=Path(__file__).resolve().parents[1]/'data/reference/D5904729_274.nc'
    with xr.open_dataset(source) as raw: ds=raw.load()
    ds['CHLA']=xr.full_like(ds.TEMP,.5);ds.CHLA.attrs['units']='mg/m3'
    ds['CHLA_QC']=xr.full_like(ds.TEMP_QC,b'1')
    ds['CHLA_ADJUSTED']=xr.full_like(ds.TEMP,99.)
    ds['CHLA_ADJUSTED_QC']=xr.full_like(ds.TEMP_QC,b'4')
    ds=ds.drop_vars(['STATION_PARAMETERS','PARAMETER_DATA_MODE'],errors='ignore')
    ds['STATION_PARAMETERS']=(('N_PROF','N_PARAM_MODE'),np.array([[b'PRES',b'TEMP',b'PSAL',b'CHLA']],dtype='S4'))
    ds['PARAMETER_DATA_MODE']=(('N_PROF','N_PARAM_MODE'),np.array([[b'D',b'D',b'D',b'R']],dtype='S1'))
    path=tmp_path/'bgc.nc';ds.to_netcdf(path)
    rows=[r for r in parse_argo(path)[0]['samples'] if r['variable']=='chlorophyll']
    assert len(rows)==1001 and all(r['value']==.5 and r['qc']==1 and not r['adjusted'] for r in rows)
    ds.CHLA.attrs['units']='unknown';ds.to_netcdf(path)
    with pytest.raises(ValueError,match='CHLA must explicitly'):parse_argo(path)


def test_published_threshold_methods_distinguish_warming_and_cooling():
    z=[0,10,20,30,40,60,80]
    t=[28,28,28.3,28.2,28,27.5,27]
    s=[34,34,34.2,34.4,34.5,34.6,34.7]
    d=column_diagnostics(z,t,s,86,3)
    assert d['temperature_departure_depth']['depth_m']<20
    assert d['barrier_layer']['cooling_depth']['depth_m']>40
    assert d['barrier_layer']['equivalent_density_delta_kg_m3'] != pytest.approx(.03)
    assert d['barrier_layer']['signed_thickness_m']>0


def test_netcdf_native_grid_roundtrip_preserves_science(case):
    model,_=case
    content=subset_netcdf(model,'temperature',0,maximum_depth=200)
    with xr.open_dataset(io.BytesIO(content)) as ds:
        assert ds.attrs['Conventions']=='CF-1.10'
        assert ds.depth.attrs['positive']=='down'
        assert ds.temperature.attrs['units']=='degree_Celsius'
        assert ds.sizes['time']==1
        np.testing.assert_allclose(ds.temperature.values,model.ds.temperature.isel(time=slice(0,1)).sel(depth=slice(0,200)).values,equal_nan=True)
    with pytest.raises(ValueError,match='no source cells'):subset_netcdf(model,'temperature',0,[0,0,1,1])


def test_coverage_json_axes_masks_and_unit(case):
    model,profiles=case;p=profiles[0]
    cov=coverage_json(model,'temperature',p['longitude'],p['latitude'],0)
    assert cov['domain']['domainType']=='VerticalProfile'
    assert cov['ranges']['temperature']['axisNames']==['z']
    assert cov['ranges']['temperature']['shape']==[model.ds.sizes['depth']]
    assert cov['domain']['referencing'][1]['system']['cs']['csAxes'][0]['direction']=='down'
    outside=coverage_json(model,'temperature',0,0,0)
    assert all(x is None for x in outside['ranges']['temperature']['values'])
    schema=json.loads((Path(__file__).parent/'schemas/coveragejson.json').read_text())
    for result in (cov,outside): jsonschema.validate(result,schema)


def test_upper_ocean_resampling_uses_native_brackets_and_leaves_analysis_unchanged(case):
    model,profiles=case
    volume=model.volume('temperature',0,maximum_depth=500)
    assert volume['axes']['depth'][-1]==500 and volume['dimensions'][2]==72
    z,y,x=np.meshgrid(volume['axes']['depth'],volume['axes']['latitude'],volume['axes']['longitude'],indexing='ij')
    # Coordinates retain their precision; only scalar display values round to 5 decimals.
    expected=model.sample('temperature',x,y,z,model.ds.time.values[0])
    actual=np.array([np.nan if v is None else v for v in volume['values']])
    np.testing.assert_allclose(actual,expected,rtol=0,atol=5.01e-6,equal_nan=True)
    assert model.ds.depth.max()==4000
    assert compare(model,profiles[0],'temperature')['metrics']['count']==1001
