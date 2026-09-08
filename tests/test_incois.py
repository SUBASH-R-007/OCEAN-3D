from pathlib import Path
import json,io
import numpy as np
import pytest
import xarray as xr
from jsonschema import validate
from backend.incois import convert,load_incois,support_summary
from backend.diagnostics import diagnose_model
from backend.exports import coverage_json,subset_netcdf

FOLDER=Path(__file__).resolve().parents[1]/'data'/'incois'

def test_official_source_is_preserved_without_inventing_temperature_convention():
    model,_=load_incois()
    with xr.open_dataset(FOLDER/'source.nc') as raw:
        np.testing.assert_allclose(model.ds.analyzed_temperature.values,raw.T_ANALYZED.transpose('time','ZAX','latitude','longitude').values,equal_nan=True)
        np.testing.assert_allclose(model.ds.salinity.values,raw.S_ANALYZED.values,equal_nan=True)
        np.testing.assert_allclose(model.ds.temperature_spread.values,raw.T_STDEV.values,equal_nan=True)
    assert 'temperature' not in model.ds
    assert 'standard_name' not in model.ds.analyzed_temperature.attrs
    assert model.ds.sizes['depth']==24
    assert not model.provenance['synthetic']
    with pytest.raises(ValueError,match='potential temperature'): diagnose_model(model,87.5,13.5,0)

def test_monthly_source_never_interpolates_across_a_month_as_an_instantaneous_field():
    model,_=load_incois()
    assert np.isnan(model.sample('salinity',87.5,13.5,10,'2026-05-25')[0])
    assert np.isfinite(model.sample('salinity',87.5,13.5,10,'2026-05-15')[0])

def test_source_contract_rejects_changed_units_and_noninteger_counts():
    with xr.open_dataset(FOLDER/'source.nc') as raw:
        changed=raw.copy(deep=True)
        changed.ZAX.attrs['units']='dbar'
        with pytest.raises(ValueError,match='metres'): convert(changed)
        changed=raw.copy(deep=True)
        valid=np.argwhere(np.isfinite(changed.T_ANALYZED.values))[0]
        changed.T_ROIOBS.values[tuple(valid)]=1.5
        with pytest.raises(ValueError,match='integers'): support_summary(changed)

def test_source_support_is_native_not_render_grid_coverage():
    model,_=load_incois()
    assert [s['valid_cells'] for s in model.provenance['support_by_time']]==[4363,4002,4564]
    assert model.provenance['support_by_time'][2]['cells_with_local_observations']==1043

def test_dense_display_matches_native_interpolation_and_preserves_masks():
    model,_=load_incois()
    volume=model.volume('analyzed_temperature',2,maximum_depth=500)
    assert volume['dimensions']==[36,36,72]
    z,y,x=np.meshgrid(volume['axes']['depth'],volume['axes']['latitude'],volume['axes']['longitude'],indexing='ij')
    expected=model.sample('analyzed_temperature',x.ravel(),y.ravel(),z.ravel(),model.ds.time.values[2])
    actual=np.asarray([np.nan if v is None else v for v in volume['values']])
    np.testing.assert_allclose(actual,expected,atol=6e-6,equal_nan=True)
    assert np.isnan(actual).any()

def test_source_specific_exports_do_not_claim_a_false_cf_standard_name():
    model,_=load_incois()
    schema=json.loads((Path(__file__).parent/'schemas'/'coveragejson.json').read_text())
    for variable in ['analyzed_temperature','temperature_spread','salinity']:
        cov=coverage_json(model,variable,87.5,13.5,0)
        validate(cov,schema)
        prop=cov['parameters'][variable]['observedProperty']
        assert ('id' in prop)==(variable=='salinity')
        with xr.open_dataset(io.BytesIO(subset_netcdf(model,variable,0))) as restored:
            assert ('standard_name' in restored[variable].attrs)==(variable=='salinity')
            np.testing.assert_allclose(restored[variable].values,model.ds[variable].values[:1],equal_nan=True)
