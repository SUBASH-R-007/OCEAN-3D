from pathlib import Path
import json
import shutil
import numpy as np
import pytest
import xarray as xr
import gsw
from fastapi.testclient import TestClient
from backend import api
from backend.analysis import compare
from backend.demo import build_demo
from backend.instrument_sources import load_instrument_cases, parse_imos_glider, parse_cchdo_ctd

FOLDER=Path(__file__).resolve().parents[1]/'data/instruments'


@pytest.fixture(scope='module')
def cases():return load_instrument_cases()


def test_native_subsets_preserve_original_samples_and_masks():
    for short,dim,indices in [('glider','TIME',None),('ctd','N_PROF',[10,40,70,100])]:
        with xr.open_dataset(FOLDER/f'{short}-original.nc') as original, xr.open_dataset(FOLDER/f'{short}-native-subset.nc') as subset:
            if indices is None:indices=np.flatnonzero(np.isin(original.PROFILE.values,[10,11,12,13]))
            selected=original.isel({dim:indices})
            for key in (['TIME','LONGITUDE','LATITUDE','DEPTH','PRES','TEMP','PSAL','CPHL','TEMP_quality_control','PSAL_quality_control','CPHL_quality_control'] if short=='glider' else ['time','longitude','latitude','pressure','ctd_temperature','ctd_salinity','ctd_temperature_qc','ctd_salinity_qc']):
                np.testing.assert_array_equal(selected[key].values,subset[key].values)


def test_real_glider_preserves_sample_positions_times_values_and_gaps(cases):
    profiles=[p for p in cases if p['instrument']=='Glider']
    assert len(profiles)==4 and all(not p['synthetic'] for p in profiles)
    with xr.open_dataset(FOLDER/'glider-native-subset.nc') as source:
        for profile in profiles:
            assert len({p['longitude'] for p in profile['path']})>1
            assert profile['path'][0]['time']!=profile['path'][-1]['time']
            assert profile['phase'] in ('descent','ascent')
            for row in profile['samples']:
                j=row['source_index'];assert row['longitude']==float(source.LONGITUDE[j]);assert row['latitude']==float(source.LATITUDE[j])
                assert row['depth']==float(source.DEPTH[j])
                if row['variable']=='salinity':assert row['value']==float(source.PSAL[j])
                if row['variable']=='chlorophyll':
                    assert row['source_qc']==float(source.CPHL_quality_control[j])
                    if np.isfinite(source.CPHL[j]):assert row['value']==float(source.CPHL[j])
                    else:assert row['value'] is None
            sample=next(r for r in profile['samples'] if r['variable']=='temperature')
            j=sample['source_index'];sa=gsw.SA_from_SP(float(source.PSAL[j]),float(source.PRES[j]),sample['longitude'],sample['latitude'])
            assert sample['value']==pytest.approx(gsw.pt0_from_t(sa,float(source.TEMP[j]),float(source.PRES[j])),abs=1e-12)


def test_real_ctd_flags_pressure_conversion_and_provenance(cases):
    profiles=[p for p in cases if p['instrument']=='CTD']
    assert len(profiles)==4
    with xr.open_dataset(FOLDER/'ctd-native-subset.nc') as source:
        for i,profile in enumerate(profiles):
            assert not profile['synthetic'] and profile['latitude']==float(source.latitude[i])
            assert len(profile['sha256'])==64
            for row in profile['samples']:
                j=row['source_index']
                assert row['depth']==pytest.approx(-gsw.z_from_p(float(source.pressure[i,j]),profile['latitude']),abs=1e-10)
                if row['variable']=='salinity':
                    assert row['source_qc']==float(source.ctd_salinity_qc[i,j])
                    assert row['qc']==({2:1,3:3,4:4,5:9,9:9}.get(row['source_qc'],0))
                    if np.isfinite(source.ctd_salinity[i,j]):assert row['value']==float(source.ctd_salinity[i,j])


def test_real_bgc_qc_is_not_promoted_and_unknown_model_variable_remains_observable(cases):
    model,_=build_demo()
    try:
        incois=next(p for p in cases if p['id']=='2902273-159-0')
        strict=compare(model,incois,'chlorophyll','strict');relaxed=compare(model,incois,'chlorophyll','lenient')
        assert strict['pairs']==[] and len(relaxed['pairs'])==58
        assert all(r['qc']==2 for r in relaxed['pairs'])
        bgc=next(p for p in cases if p['id']=='2903464-7-0')
        assert len(compare(model,bgc,'chlorophyll')['pairs'])==504
        model.ds=model.ds.drop_vars('chlorophyll')
        unmatched=compare(model,bgc,'chlorophyll')
        assert len(unmatched['pairs'])==504 and unmatched['metrics']['count']==0
        assert unmatched['comparison_reason'] and all(p['model'] is None for p in unmatched['pairs'])
    finally:model.close()


def test_moving_comparison_queries_each_native_sample(cases):
    profile=next(p for p in cases if p['instrument']=='Glider')
    class Probe:
        ds=xr.Dataset({'salinity': ('sample',[34.])});provenance={}
        def sample(self,variable,lon,lat,depth,time,gap):
            self.query=(lon,lat,depth,time)
            return np.full(len(depth),34.)
    probe=Probe();result=compare(probe,profile,'salinity')
    assert len(set(probe.query[0]))>1 and len(set(probe.query[3]))>1
    for pair,x,y,t in zip(result['pairs'],probe.query[0],probe.query[1],probe.query[3]):
        assert (pair['longitude'],pair['latitude'],pair['time'].removesuffix('Z'))==(x,y,t)


def test_native_adapters_reject_wrong_units(tmp_path):
    for filename,variable,parser in [('glider-native-subset.nc','TEMP',parse_imos_glider),('ctd-native-subset.nc','ctd_temperature',parse_cchdo_ctd)]:
        with xr.open_dataset(FOLDER/filename) as source:ds=source.load()
        ds[variable].attrs['units']='kelvin';path=tmp_path/filename;ds.to_netcdf(path)
        with pytest.raises(ValueError,match='units'):parser(path)


def test_instrument_api_across_incois_and_hycom(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'DATA',tmp_path)
    with TestClient(api.app) as client:
        catalog=client.get('/api/catalog').json()
        real=[p for p in catalog['profiles'] if not p['synthetic']]
        assert {'Argo','Glider','CTD','BGC Argo'} <= {p['instrument'] for p in real}
        for model in ['incois-mnt-mccreary-latest','hycom-currents-indian']:
            for identity,variable in [('IMOS-SG152-10','temperature'),('CCHDO-325020250321-64-1','salinity'),('2903464-7-0','chlorophyll')]:
                response=client.get(f'/api/profiles/{identity}',params={'model':model,'variable':variable})
                assert response.status_code==200,response.text
                data=response.json();assert data['pairs'] and data['samples']
                assert data['profile']['id']==identity and data['metrics']['count']==0
                assert data['comparison_reason']
        assert {'imos-glider','cchdo-ctd'} <= set(client.get('/api/adapters').json()['observations'])
        for kind,filename in [('imos-glider','glider-native-subset.nc'),('cchdo-ctd','ctd-native-subset.nc')]:
            response=client.post('/api/import',params={'kind':kind},files={'file':(filename,(FOLDER/filename).read_bytes(),'application/x-netcdf')})
            assert response.status_code==201,response.text
            identity=response.json()['id'];assert (tmp_path/(identity+'.nc')).is_file()
            imported=[p for p in client.get('/api/catalog').json()['profiles'] if p['id'].startswith(identity+':')]
            assert len(imported)==4 and all(not p['synthetic'] for p in imported)


def test_normalized_cache_detects_tampering(tmp_path,cases):
    from backend.science import file_hash
    original=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    item=next(item for item in original['sources'] if item['file']=='bgc-incois.nc')
    shutil.copy2(FOLDER/item['file'],tmp_path/item['file'])
    cache=tmp_path/'profiles.json';cache.write_text(json.dumps([next(p for p in cases if p['id']=='2902273-159-0')]),encoding='utf-8')
    (tmp_path/'manifest.json').write_text(json.dumps({'sources':[item],'normalized':{'file':cache.name,'sha256':file_hash(cache)}}),encoding='utf-8')
    assert load_instrument_cases(tmp_path)[0]['id']=='2902273-159-0'
    with cache.open('a',encoding='utf-8') as stream:stream.write('\n')
    with pytest.raises(ValueError,match='cache checksum'):load_instrument_cases(tmp_path)
