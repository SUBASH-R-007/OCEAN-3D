import numpy as np
import pytest
from backend.science import multilinear
from backend.diagnostics import crossing, column_diagnostics, diagnose_model
from backend.demo import build_demo


def test_missing_zero_weight_corner_does_not_erase_exact_node():
    a = np.array([[1., np.nan],[3.,4.]])
    v = multilinear([[0,1],[0,1]], a, [[0,0],[.5,0],[.5,.5],[2,0]])
    assert v[0] == 1 and v[1] == 2
    assert np.isnan(v[2:]).all()


def test_single_timestamp_only_supports_exact_instant():
    a = np.array([[5.,7.]])
    out = multilinear([[12],[0,1]], a, [[12,.5],[11,.5]])
    assert out[0] == 6 and np.isnan(out[1])


def test_threshold_interpolation_and_censoring():
    assert crossing([0,10,20,30],[25,25,25.01,25.05],10,.03)['depth_m'] == pytest.approx(25)
    assert crossing([10,20,30],[25,np.nan,26],10,.03)['status']=='gap_before_crossing'
    assert crossing([10,200],[25,26],10,.03)['status']=='gap_before_crossing'
    assert crossing([20,30],[25,26],10,.03)['status']=='reference_unavailable'
    assert crossing([10,20],[25,25],10,.03)['depth_m'] is None


def test_teos_against_published_gsw_reference():
    import gsw
    sa=np.array([34.7118,34.8915,35.0256,34.8472,34.7366,34.7324])
    ct=np.array([28.8099,28.4392,22.7862,10.2262,6.8272,4.3236])
    expected=[21.797900819337656,22.052215404397316,23.892985307893923,26.667608665972011,27.107380455119710,27.409748977090885]
    np.testing.assert_allclose(gsw.sigma0(sa,ct),expected,atol=1e-10)


def test_constant_column_has_censored_mld_not_bottom_or_zero():
    result=column_diagnostics([0,10,20,40,80], [28]*5, [35]*5,85,14)
    assert result['density_mld']['depth_m'] is None
    assert result['temperature_departure_depth']['depth_m'] is None


def test_model_diagnostics_record_native_bracket_and_provenance():
    model,_=build_demo()
    result=diagnose_model(model,85.2,14.8,2)
    assert result['provenance']['synthetic']
    assert result['density_mld']['status']=='resolved'
    a,b=result['density_mld']['bracket_m']
    assert a<=result['density_mld']['depth_m']<=b
    assert len(result['density_threshold_sensitivity'])==3
