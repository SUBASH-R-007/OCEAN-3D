"""Interchange encodings. These endpoints do not claim full OGC EDR conformance."""
import numpy as np
import json
from .science import VARIABLES, clean


def coverage_json(model, variable, longitude, latitude, index):
    if index<0 or index>=model.ds.sizes['time']:
        raise ValueError('Time index unavailable.')
    if variable not in model.ds:
        raise ValueError('Variable unavailable.')
    depths=model.ds.depth.values
    if len(depths)>2000: raise ValueError('Export exceeds 2000 depth levels.')
    values=model.sample(variable,longitude,latitude,depths,model.ds.time.values[index])
    meta=VARIABLES[variable]
    return dict(type='Coverage',domain=dict(type='Domain',domainType='VerticalProfile',
        axes=dict(x=dict(values=[longitude]),y=dict(values=[latitude]),z=dict(values=clean(depths)),t=dict(values=[model.catalog()['times'][index]])),
        referencing=[dict(coordinates=['x','y'],system=dict(type='GeographicCRS',id='http://www.opengis.net/def/crs/OGC/1.3/CRS84')),
                     dict(coordinates=['z'],system=dict(type='VerticalCRS',cs=dict(csAxes=[dict(name=dict(en='Depth'),direction='down',unit=dict(symbol='m'))]))),
                     dict(coordinates=['t'],system=dict(type='TemporalRS',calendar='Gregorian'))]),
        parameters={variable:dict(type='Parameter',description=dict(en=meta['label']),unit=dict(symbol=meta['unit']),observedProperty={**({'id':'http://vocab.nerc.ac.uk/standard_name/'+meta['standard']+'/'} if meta['standard'] else {}),'label':dict(en=meta['label'])})},
        ranges={variable:dict(type='NdArray',dataType='float',axisNames=['z'],shape=[len(depths)],values=clean(values))},
        ocean3d=dict(provenance=model.provenance,method='Bounded horizontal interpolation at native model depth and exact selected timestamp; missing contributing corners preserved.'))


def subset_netcdf(model, variable, index, bounds=None, maximum_depth=None):
    if variable not in model.ds or not 0<=index<model.ds.sizes['time']:
        raise ValueError('Variable or time index unavailable.')
    ds=model.ds[[variable]].isel(time=slice(index,index+1))
    if bounds:
        if len(bounds)!=4 or not np.isfinite(bounds).all() or not (-180<=bounds[0]<bounds[2]<=180 and -90<=bounds[1]<bounds[3]<=90):
            raise ValueError('bbox requires west,south,east,north.')
        ds=ds.sel(longitude=slice(bounds[0],bounds[2]),latitude=slice(bounds[1],bounds[3]))
    if maximum_depth is not None: ds=ds.sel(depth=slice(0,maximum_depth))
    if any(n==0 for n in ds.sizes.values()): raise ValueError('Requested subset contains no source cells.')
    if ds[variable].size>2_000_000: raise ValueError('Export limit: 2 million cells. Narrow bbox or maximum depth.')
    ds=ds.copy(deep=False)
    ds.attrs=dict(Conventions='CF-1.10',title=model.provenance['title'],source=model.provenance.get('source',''),
                  history='Ocean3D native-grid selection; no render resampling; selected exact model timestamp.',synthetic=str(model.provenance.get('synthetic',False)).lower())
    if model.provenance.get('product'):
        product=model.provenance['product']
        ds.attrs.update(ocean3d_product_id=product['id'],ocean3d_product_version=product['version'],
                        ocean3d_lineage=json.dumps(product['lineage']),ocean3d_product_metadata=json.dumps(product))
    for key,attrs in [('longitude',dict(units='degrees_east',standard_name='longitude')),('latitude',dict(units='degrees_north',standard_name='latitude')),('depth',dict(units='m',positive='down',standard_name='depth')),('time',dict(standard_name='time'))]:
        ds[key].attrs=attrs
    meta=VARIABLES[variable]
    ds[variable].attrs=dict(long_name=meta['label'],units=meta.get('canonical_unit') or {'temperature':'degree_Celsius','analyzed_temperature':'degree_Celsius','temperature_spread':'degree_Celsius','salinity':'1','chlorophyll':'mg m-3','u':'m s-1','v':'m s-1'}[variable])
    if meta['standard']: ds[variable].attrs['standard_name']=meta['standard']
    # NETCDF3_64BIT preserves broad interoperability without a filesystem stage.
    return bytes(ds.to_netcdf(engine='scipy',format='NETCDF3_64BIT'))
