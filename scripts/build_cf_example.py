"""Reproducible synthetic CF trajectoryProfile example. Never labeled observed data."""
from pathlib import Path
import numpy as np
import xarray as xr
from backend.demo import build_demo


def example():
    model, _ = build_demo()
    lon = np.array([85., 85.12, 85.25, 85.38]); lat = np.array([14., 14.08, 14.16, 14.22])
    times = np.array(['2025-09-03T06:00', '2025-09-03T09:00', '2025-09-03T12:00', '2025-09-03T15:00'], dtype='datetime64[ns]')
    depths = np.tile([5., 25., 50., 100., 150., 250., 400.], 4)
    ds = xr.Dataset({'profile_id': ('profile', ['TRAINING-01', 'TRAINING-02', 'TRAINING-03', 'TRAINING-04'], {'cf_role':'profile_id'}),
        'trajectory_id': ('trajectory', ['SYNTHETIC-GLIDER'], {'cf_role':'trajectory_id'}),
        'trajectory_index': ('profile', np.zeros(4,dtype='int32'), {'instance_dimension':'trajectory'}),
        'row_size': ('profile', np.full(4,7,dtype='int32'), {'sample_dimension':'obs'}),
        'longitude': ('profile', lon, {'standard_name':'longitude','units':'degrees_east'}),
        'latitude': ('profile', lat, {'standard_name':'latitude','units':'degrees_north'}),
        'time': ('profile', times, {'standard_name':'time'}),
        'depth': ('obs', depths, {'standard_name':'depth','units':'m','positive':'down'})},
        attrs={'Conventions':'CF-1.10','featureType':'trajectoryProfile','instrument':'Glider','synthetic':'true','title':'Synthetic training mission; not instrument observations'})
    for variable, standard, unit in [('thetao','sea_water_potential_temperature','degree_Celsius'),('so','sea_water_salinity','1'),('chl','mass_concentration_of_chlorophyll_a_in_sea_water','mg m-3')]:
        key={'thetao':'temperature','so':'salinity','chl':'chlorophyll'}[variable]
        vals=model.sample(key,np.repeat(lon,7),np.repeat(lat,7),depths,np.repeat(times,7))
        ds[variable]=('obs', vals, {'standard_name':standard,'units':unit,'coordinates':'time latitude longitude depth','ancillary_variables':variable+'_qc'})
        flags=np.ones(28,dtype='int8');flags[5]=4
        ds[variable+'_qc']=('obs', flags, {'flag_values':np.array([0,1,2,4,9],dtype='int8'),'flag_meanings':'unknown good_data probably_good_data bad_data missing_data'})
    model.close()
    return ds


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    for parent in [root/'data/examples',root/'web/public/examples']:
        parent.mkdir(parents=True,exist_ok=True)
        example().to_netcdf(parent/'synthetic-glider.nc',engine='scipy',format='NETCDF3_64BIT')
    print('Wrote explicitly synthetic CF mission: four profiles, 28 depths, three variables.')
