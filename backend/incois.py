"""INCOIS Argo objective analysis, with source temperature semantics preserved.

The official product does not declare in-situ versus potential temperature.
It must never silently enter potential-temperature diagnostics or comparisons.
"""
from pathlib import Path
import json
import numpy as np
import xarray as xr
from .science import Model, normalize, file_hash

DATASET_ID='incois_argo_mnt_McCreary'
INFO_URL=f'https://erddap.incois.gov.in/erddap/info/{DATASET_ID}/index.html'
REPORT_URL='https://argo.ucsd.edu/wp-content/uploads/sites/361/2020/05/Incois_Argo_ObjectiveAnalysis_Ver2.0.pdf'


def convert(source):
    required={'T_ANALYZED','S_ANALYZED','T_STDEV','T_ROIOBS','T_BOXOBS'}
    if not required.issubset(source): raise ValueError('Incomplete INCOIS objective-analysis product.')
    if source.attrs.get('institution')!='INCOIS': raise ValueError('Expected INCOIS institution metadata.')
    if source.ZAX.attrs.get('units','').lower()!='meters': raise ValueError('Expected INCOIS depth in metres.')
    if source.T_ANALYZED.attrs.get('units')!='degs' or source.T_STDEV.attrs.get('units')!='degs':
        raise ValueError('INCOIS temperature metadata changed; review the adapter.')
    if source.S_ANALYZED.attrs.get('standard_name')!='sea_water_practical_salinity' or source.S_ANALYZED.attrs.get('units')!='PSU':
        raise ValueError('Expected explicitly identified practical salinity.')
    for name in required:
        if source[name].dims!=('time','ZAX','latitude','longitude'): raise ValueError('Unexpected INCOIS grid layout.')
    ds=source.rename({'ZAX':'depth'})
    result=xr.Dataset(coords={k:ds[k] for k in ('time','depth','latitude','longitude')})
    # Celsius is supported by the product report. Thermodynamic convention is
    # deliberately unspecified, rather than inventing a CF standard_name.
    for target,name,label in [('analyzed_temperature','T_ANALYZED','INCOIS analyzed temperature; thermodynamic convention unspecified'),
                              ('temperature_spread','T_STDEV','INCOIS temperature standard deviation about the analyzed mean')]:
        result[target]=ds[name].copy()
        result[target].attrs=dict(units='degree_Celsius',long_name=label,source_variable=name)
    result['salinity']=ds.S_ANALYZED.copy()
    result.salinity.attrs=dict(units='1',standard_name='sea_water_salinity',source_variable='S_ANALYZED')
    result.depth.attrs=dict(units='m',positive='down',standard_name='depth')
    result.attrs=dict(Conventions='CF-1.10',title='INCOIS Argo · Bay of Bengal · May–July 2026',synthetic='false',
                      history='Bounded native-grid ERDDAP subset. Decode source fill values. Preserve analyzed temperature without assigning an unverified thermodynamic definition.')
    return normalize(result)


def support_summary(source):
    result=[]
    for index,date in enumerate(source.time.values):
        frame=source.isel(time=index)
        wet=np.isfinite(frame.T_ANALYZED.values)
        roi=frame.T_ROIOBS.values[wet];box=frame.T_BOXOBS.values[wet]
        if np.any(np.isfinite(roi)&((roi<0)|(roi!=np.floor(roi)))) or np.any(np.isfinite(box)&((box<0)|(box!=np.floor(box)))):
            raise ValueError('Source observation counts are not nonnegative integers.')
        def count_range(a):
            finite=a[np.isfinite(a)]
            return [int(finite.min()),int(finite.max())] if finite.size else []
        result.append(dict(time=np.datetime_as_string(date,unit='s')+'Z',valid_cells=int(wet.sum()),total_cells=int(wet.size),
                           cells_with_local_observations=int(np.count_nonzero(box>0)),
                           roi_count_range=count_range(roi),local_count_range=count_range(box)))
    return result


def load_incois():
    folder=Path(__file__).resolve().parents[1]/'data'/'incois'
    if not (folder/'case.json').is_file(): return None
    info=json.loads((folder/'case.json').read_text(encoding='utf-8'))
    for name,key in [('model.nc','sha256'),('source.nc','source_sha256')]:
        if file_hash(folder/name)!=info['provenance'][key]: raise ValueError('INCOIS dataset checksum differs from its manifest.')
    with xr.open_dataset(folder/'model.nc') as ds: model=Model(info['id'],normalize(ds).load(),info['provenance'])
    return model,[]
