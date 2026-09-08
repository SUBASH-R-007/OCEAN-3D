"""Generate small, explicitly synthetic files exercising extension contracts."""
from pathlib import Path
import hashlib
import json
import numpy as np
import xarray as xr


def write_examples(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    header='profile_id,instrument,longitude,latitude,time,depth,variable,value,unit,qc,synthetic\n'
    cases={
        'synthetic-mooring.csv':('# ocean3d:mooring-v1\n','Mooring',50,[28.0,27.5,27.2]),
        'synthetic-adcp.csv':('# ocean3d:adcp-earth-v1\n','ADCP',None,None),
        'synthetic-hf-radar.csv':('# ocean3d:hf-total-earth-v1\n','HF radar',0,None),
    }
    for filename,(contract,instrument,depth,values) in cases.items():
        rows=[]
        for step,hour in enumerate((0,6,12)):
            date=f'2025-09-03T{hour:02d}:00:00Z'
            for z in ([20,50,100] if instrument=='ADCP' else [depth]):
                readings={'temperature':values[step]} if values else {'u':20-step*5-z*.1,'v':-10+step*3}
                for variable,value in readings.items():
                    unit='degree_Celsius' if variable=='temperature' else 'cm/s'
                    qc=4 if step==1 and variable=='v' else 1
                    rows.append(f'TRAINING-{instrument.replace(" ","-")},{instrument},85,14,{date},{z},{variable},{value},{unit},{qc},true\n')
        (directory/filename).write_text(contract+header+''.join(rows),encoding='utf-8')
    values=np.linspace(-1,1,3*4*4*4,dtype='float32').reshape(3,4,4,4)
    values[1,1,1,1]=np.nan
    source_bytes=b'Ocean3D synthetic analytic fixture; not a trained ML model.'
    lineage=dict(generated_at='2026-09-08T00:00:00Z',
        inputs=[{'id':'synthetic-contract-input','sha256':hashlib.sha256(source_bytes).hexdigest()}],
        artifact_sha256=hashlib.sha256(b'No model artifact: synthetic interface test.').hexdigest(),
        training_data='None. This analytic fixture only tests the ML-output data contract.',
        inference_domain='Synthetic 84–86 E, 13–15 N, 0–300 m; 3–5 September 2025.',
        validation='Not validated for prediction. No trained ML model was used.',
        limitations='Synthetic values must not be interpreted as forecasts or observed anomalies.')
    ds=xr.Dataset({'ml_temperature_anomaly':(('time','depth','latitude','longitude'),values,
        {'units':'degree_Celsius','long_name':'Synthetic ML-output interface temperature anomaly'})},
        coords={'time':np.array(['2025-09-03','2025-09-04','2025-09-05'],dtype='datetime64[ns]'),
                'depth':('depth',[0.,100.,200.,300.],{'units':'m','positive':'down'}),
                'latitude':('latitude',np.linspace(13,15,4),{'units':'degrees_north'}),
                'longitude':('longitude',np.linspace(84,86,4),{'units':'degrees_east'})},
        attrs={'Conventions':'CF-1.10','synthetic':'true','ocean3d_product_id':'ml-anomaly-example',
               'ocean3d_product_version':'1.0.0','ocean3d_lineage':json.dumps(lineage)})
    ds.to_netcdf(directory/'synthetic-ml-output.nc',engine='scipy')
    return directory


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('tmp/extension-examples'))
    print(write_examples(parser.parse_args().output))
