"""Bounded WMS 1.3.0 and native-grid WCS 1.0.0 HTTP GET services.

WCS publishes one coverage per variable/native depth. No reprojection or resampling
is advertised. Conformance certification is separate from these tested operations.
"""
import struct
import zlib
import xml.etree.ElementTree as ET
import numpy as np
from fastapi import APIRouter, Request
from fastapi.responses import Response, JSONResponse
from .science import VARIABLES
from .exports import subset_netcdf

router = APIRouter()
WMS = 'http://www.opengis.net/wms'
WCS = 'http://www.opengis.net/wcs'
GML = 'http://www.opengis.net/gml'
XLINK = 'http://www.w3.org/1999/xlink'
OGC = 'http://www.opengis.net/ogc'
for prefix, namespace in [('wms', WMS), ('wcs', WCS), ('gml', GML), ('xlink', XLINK), ('ogc', OGC)]: ET.register_namespace(prefix, namespace)
PALETTES = {'thermal': ['#18265c', '#196ea0', '#21b5ad', '#d7da6c', '#f3944b', '#a92e50'], 'saline': ['#10244c', '#236b91', '#49aaab', '#d6ecb6'], 'balance': ['#2859a3', '#80b7d5', '#eceae2', '#e5a575', '#b84044']}


class ServiceError(ValueError):
    def __init__(self, code, message, locator=None):
        super().__init__(message); self.code = code; self.locator = locator


def el(parent, ns, tag, value=None, **attrs):
    e = ET.SubElement(parent, f'{{{ns}}}{tag}', {k: str(v) for k,v in attrs.items()})
    if value is not None: e.text = str(value)
    return e


def xml(root, status=200):
    return Response(ET.tostring(root, encoding='utf-8', xml_declaration=True), media_type='text/xml', status_code=status)


def params(request):
    out = {}
    for key, value in request.query_params.multi_items():
        key = key.upper()
        if key in out: raise ServiceError('InvalidParameterValue', 'Duplicate parameter.', key)
        out[key] = value
    return out


def required(p, key):
    if not p.get(key): raise ServiceError('MissingParameterValue', f'{key} is required.', key)
    return p[key]


def number(p, key, default=None):
    try: v = float(p.get(key, default))
    except (TypeError, ValueError): raise ServiceError('InvalidParameterValue', f'{key} must be numeric.', key)
    if not np.isfinite(v): raise ServiceError('InvalidParameterValue', f'{key} must be finite.', key)
    return v


def bounds(p, wms=False):
    crs = required(p, 'CRS')
    if crs not in ('EPSG:4326', 'CRS:84') or (not wms and crs != 'EPSG:4326'):
        raise ServiceError('InvalidCRS', 'Unsupported CRS.', 'CRS')
    try: b = [float(v) for v in required(p, 'BBOX').split(',')]
    except ValueError: raise ServiceError('InvalidParameterValue', 'Invalid BBOX.', 'BBOX')
    if len(b) != 4: raise ServiceError('InvalidParameterValue', 'BBOX needs four coordinates.', 'BBOX')
    # WMS 1.3 EPSG:4326 uses latitude/longitude; WCS 1.0 uses x/y.
    if wms and crs == 'EPSG:4326': b = [b[1], b[0], b[3], b[2]]
    if not np.isfinite(b).all() or not (-180 <= b[0] < b[2] <= 180 and -90 <= b[1] < b[3] <= 90):
        raise ServiceError('InvalidParameterValue', 'Invalid geographic BBOX.', 'BBOX')
    return b


def layer(models, identifier, depth=False):
    parts = identifier.split(':')
    if len(parts) != (3 if depth else 2) or parts[0] not in models or parts[1] not in models[parts[0]].ds:
        raise ServiceError('CoverageNotDefined' if depth else 'LayerNotDefined', 'Unknown layer or coverage.')
    m = models[parts[0]]; variable = parts[1]; zi = None
    if depth:
        try: zi = int(parts[2])
        except ValueError: raise ServiceError('CoverageNotDefined', 'Invalid depth index.')
        if zi < 0 or zi >= m.ds.sizes['depth']: raise ServiceError('CoverageNotDefined', 'Depth index unavailable.')
    return m, variable, zi


def time_index(m, p):
    if 'TIME' not in p: return m.ds.sizes['time'] - 1
    try:
        if not p['TIME'].endswith('Z'): raise ValueError()
        date = np.datetime64(p['TIME'][:-1], 'ns')
        indices = np.flatnonzero(m.ds.time.values.astype('datetime64[ns]') == date)
    except ValueError: raise ServiceError('InvalidDimensionValue', 'TIME must be one advertised UTC timestamp.', 'TIME')
    if len(indices) != 1: raise ServiceError('InvalidDimensionValue', 'TIME must be one advertised timestamp; no nearest-time substitution.', 'TIME')
    return int(indices[0])


def online(parent, ns, endpoint):
    el(parent, ns, 'OnlineResource', **{f'{{{XLINK}}}type': 'simple', f'{{{XLINK}}}href': endpoint+'?'})


def wms_capabilities(models, endpoint):
    if sum(len(m.ds.data_vars)*(m.ds.sizes['time']+m.ds.sizes['depth']) for m in models.values()) > 200_000:
        raise ServiceError('OperationNotSupported', 'WMS dimension metadata exceeds the service budget. Mount a smaller time archive for this service.')
    root = ET.Element(f'{{{WMS}}}WMS_Capabilities', version='1.3.0')
    service = el(root, WMS, 'Service'); el(service, WMS, 'Name', 'WMS'); el(service, WMS, 'Title', 'Ocean3D depth-resolved ocean fields')
    el(service, WMS, 'Abstract', 'Regional WMS. Exact advertised time and elevation, positive-up metres. Source masks retained; not an operational advisory service.')
    online(service, WMS, endpoint); el(service, WMS, 'Fees', 'none'); el(service, WMS, 'AccessConstraints', 'Source reuse terms apply; deployment authentication may apply.')
    el(service, WMS, 'LayerLimit', 1); el(service, WMS, 'MaxWidth', 1024); el(service, WMS, 'MaxHeight', 1024)
    cap = el(root, WMS, 'Capability'); req = el(cap, WMS, 'Request')
    for op, fmt in [('GetCapabilities', 'text/xml'), ('GetMap', 'image/png'), ('GetFeatureInfo', 'application/json')]:
        item = el(req, WMS, op); el(item, WMS, 'Format', fmt)
        online(el(el(el(item, WMS, 'DCPType'), WMS, 'HTTP'), WMS, 'Get'), WMS, endpoint)
    el(el(cap, WMS, 'Exception'), WMS, 'Format', 'XML')
    group = el(cap, WMS, 'Layer'); el(group, WMS, 'Title', 'Ocean model fields'); el(group, WMS, 'CRS', 'CRS:84'); el(group, WMS, 'CRS', 'EPSG:4326')
    for m in models.values():
        cat = m.catalog(); west, south, east, north = cat['bounds']
        for v in cat['variables']:
            item = el(group, WMS, 'Layer', queryable='1'); el(item, WMS, 'Name', f'{m.id}:{v["id"]}'); el(item, WMS, 'Title', f'{cat["title"]} · {v["label"]}')
            el(item, WMS, 'Abstract', f'{m.provenance.get("source", "")} | units={v["unit"]}; default range={v["range"]}; SHA256={m.provenance.get("sha256", "unavailable")}')
            box = el(item, WMS, 'EX_GeographicBoundingBox')
            for key, val in [('westBoundLongitude', west), ('eastBoundLongitude', east), ('southBoundLatitude', south), ('northBoundLatitude', north)]: el(box, WMS, key, val)
            el(item, WMS, 'BoundingBox', CRS='CRS:84', minx=west, miny=south, maxx=east, maxy=north)
            el(item, WMS, 'BoundingBox', CRS='EPSG:4326', minx=south, miny=west, maxx=north, maxy=east)
            el(item, WMS, 'Dimension', ','.join(cat['times']), name='time', units='ISO8601', default=cat['times'][-1], nearestValue='0')
            el(item, WMS, 'Dimension', ','.join(str(-z) for z in reversed(cat['depths'])), name='elevation', units='EPSG:5030', unitSymbol='m', default=-cat['depths'][0], nearestValue='0')
            for name in PALETTES:
                style = el(item, WMS, 'Style'); el(style, WMS, 'Name', name); el(style, WMS, 'Title', name.capitalize())
    return xml(root)


def png(values, limits, palette, transparent, background):
    rgb = np.array([[int(c[i:i+2], 16) for i in (1,3,5)] for c in PALETTES[palette]])
    valid = np.isfinite(values)
    fraction = np.clip((np.nan_to_num(values, nan=limits[0])-limits[0])/(limits[1]-limits[0]), 0, 1)*(len(rgb)-1)
    low = np.minimum(np.floor(fraction).astype(int), len(rgb)-2); mix = fraction-low
    colors = np.rint(rgb[low]*(1-mix[..., None])+rgb[low+1]*mix[..., None]).astype('uint8')
    rgba = np.concatenate([colors, np.full((*values.shape, 1), 255, dtype='uint8')], axis=-1)
    rgba[~valid] = [*background, 0 if transparent else 255]
    def chunk(name, data): return struct.pack('!I', len(data))+name+data+struct.pack('!I', zlib.crc32(name+data)&0xffffffff)
    data = b''.join(b'\x00'+row.tobytes() for row in rgba)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('!2I5B', values.shape[1], values.shape[0], 8, 6, 0, 0, 0))+chunk(b'IDAT', zlib.compress(data))+chunk(b'IEND', b'')


def map_request(models, p, feature=False):
    identifier = required(p, 'LAYERS'); m, variable, _ = layer(models, identifier)
    if required(p, 'FORMAT') != 'image/png': raise ServiceError('InvalidFormat', 'Only image/png is supported.', 'FORMAT')
    if 'STYLES' not in p: raise ServiceError('MissingParameterValue', 'STYLES is required (empty selects thermal).', 'STYLES')
    style = p['STYLES'] or 'thermal'
    if style not in PALETTES: raise ServiceError('StyleNotDefined', 'Unknown style.', 'STYLES')
    width, height = number(p, 'WIDTH'), number(p, 'HEIGHT')
    if width != int(width) or height != int(height) or not 1 <= width <= 1024 or not 1 <= height <= 1024 or width*height > 262144:
        raise ServiceError('InvalidParameterValue', 'Image limit: 1024 per side and 262,144 total pixels.')
    width, height = int(width), int(height); west, south, east, north = bounds(p, True)
    ti = time_index(m, p); z = -number(p, 'ELEVATION', -float(m.ds.depth[0]))
    matches = np.flatnonzero(np.isclose(m.catalog()['depths'], z, atol=1e-7, rtol=0))
    if len(matches) != 1:
        raise ServiceError('InvalidDimensionValue', 'ELEVATION must be an advertised negative native depth.', 'ELEVATION')
    z = float(m.ds.depth.values[matches[0]])
    # Pixel centres, with image rows north to south.
    xs = west+(np.arange(width)+.5)*(east-west)/width
    ys = north-(np.arange(height)+.5)*(north-south)/height
    if feature:
        if required(p, 'QUERY_LAYERS') != identifier: raise ServiceError('LayerNotQueryable', 'QUERY_LAYERS must equal LAYERS.')
        if required(p, 'INFO_FORMAT') != 'application/json': raise ServiceError('InvalidFormat', 'Only application/json feature info is supported.')
        i, j = number(p, 'I'), number(p, 'J')
        if i != int(i) or j != int(j) or not 0 <= i < width or not 0 <= j < height: raise ServiceError('InvalidPoint', 'Pixel is outside the image.')
        lon, lat = float(xs[int(i)]), float(ys[int(j)])
        value = m.sample(variable, lon, lat, z, m.ds.time.values[ti])[0]
        return JSONResponse(dict(layer=identifier, longitude=lon, latitude=lat, depth=z, time=m.catalog()['times'][ti], value=float(value) if np.isfinite(value) else None, unit=VARIABLES[variable]['unit'], method='Pixel-centre bounded native-grid interpolation; exact time and depth.', provenance=m.provenance))
    xx, yy = np.meshgrid(xs, ys); values = m.sample(variable, xx, yy, z, m.ds.time.values[ti]).reshape(height, width)
    limits = VARIABLES[variable]['range']
    if 'COLORSCALERANGE' in p:
        try: limits = [float(v) for v in p['COLORSCALERANGE'].split(',')]
        except ValueError: raise ServiceError('InvalidParameterValue', 'Invalid COLORSCALERANGE.')
        if len(limits) != 2 or not np.isfinite(limits).all() or limits[0] >= limits[1]: raise ServiceError('InvalidParameterValue', 'Invalid COLORSCALERANGE.')
    bg = p.get('BGCOLOR', '0xFFFFFF')
    try:
        if len(bg) != 8 or not bg.startswith('0x'): raise ValueError()
        background = [int(bg[i:i+2],16) for i in (2,4,6)]
    except ValueError: raise ServiceError('InvalidParameterValue', 'BGCOLOR must be 0xRRGGBB.')
    return Response(png(values, limits, style, p.get('TRANSPARENT', 'FALSE').upper() == 'TRUE', background), media_type='image/png')


def brief(parent, m, variable, zi, full=False, catalog=None):
    cat = catalog if catalog is not None else m.catalog(); west,south,east,north = cat['bounds']; name = f'{m.id}:{variable}:{zi}'
    item = el(parent, WCS, 'CoverageOffering' if full else 'CoverageOfferingBrief')
    el(item, WCS, 'description', f'Native depth {cat["depths"][zi]} m. Exact TIME or default latest. No resampling/reprojection; source masks preserved.')
    el(item, WCS, 'name', name); el(item, WCS, 'label', f'{cat["title"]} · {VARIABLES[variable]["label"]} · {cat["depths"][zi]} m')
    box = el(item, WCS, 'lonLatEnvelope', srsName='urn:ogc:def:crs:OGC:1.3:CRS84')
    el(box, GML, 'pos', f'{west} {south}'); el(box, GML, 'pos', f'{east} {north}')
    el(box, GML, 'timePosition', cat['times'][0]); el(box, GML, 'timePosition', cat['times'][-1])
    if full:
        domain = el(item, WCS, 'domainSet'); spatial = el(domain, WCS, 'spatialDomain')
        envelope = el(spatial, GML, 'Envelope', srsName='EPSG:4326')
        el(envelope, GML, 'pos', f'{west} {south}'); el(envelope, GML, 'pos', f'{east} {north}')
        # Grid rather than RectifiedGrid: nonuniform rectilinear grids remain valid.
        grid = el(spatial, GML, 'Grid', dimension='2'); envelope = el(el(grid, GML, 'limits'), GML, 'GridEnvelope')
        el(envelope, GML, 'low', '0 0'); el(envelope, GML, 'high', f'{m.ds.sizes["longitude"]-1} {m.ds.sizes["latitude"]-1}')
        el(grid, GML, 'axisName', 'longitude'); el(grid, GML, 'axisName', 'latitude')
        temporal = el(domain, WCS, 'temporalDomain')
        for t in cat['times']: el(temporal, GML, 'timePosition', t)
        rs = el(el(item, WCS, 'rangeSet'), WCS, 'RangeSet', refSys='urn:ocean3d:units:'+variable, refSysLabel=VARIABLES[variable]['unit'])
        el(rs, WCS, 'name', variable); el(rs, WCS, 'label', VARIABLES[variable]['label'])
        crs = el(item, WCS, 'supportedCRSs'); el(crs, WCS, 'requestResponseCRSs', 'EPSG:4326'); el(crs, WCS, 'nativeCRSs', 'EPSG:4326')
        el(el(item, WCS, 'supportedFormats', nativeFormat='NetCDF'), WCS, 'formats', 'NetCDF')
        el(el(item, WCS, 'supportedInterpolations', default='none'), WCS, 'interpolationMethod', 'none')
    return item


def wcs_request(models, p, endpoint):
    op = p['REQUEST']
    if op == 'GetCapabilities':
        if sum(len(m.ds.data_vars)*m.ds.sizes['depth'] for m in models.values()) > 4096:
            raise ServiceError('OperationNotSupported', 'WCS exceeds 4096 advertised coverages. Mount a smaller service catalog.')
        root = ET.Element(f'{{{WCS}}}WCS_Capabilities', version='1.0.0')
        service = el(root, WCS, 'Service'); el(service, WCS, 'name', 'Ocean3D WCS'); el(service, WCS, 'label', 'Ocean3D native ocean coverages')
        el(service, WCS, 'fees', 'NONE'); el(service, WCS, 'accessConstraints', 'Source reuse terms and deployment authentication apply.')
        cap = el(root, WCS, 'Capability'); req = el(cap, WCS, 'Request')
        for name in ('GetCapabilities', 'DescribeCoverage', 'GetCoverage'):
            online(el(el(el(el(req, WCS, name), WCS, 'DCPType'), WCS, 'HTTP'), WCS, 'Get'), WCS, endpoint)
        el(el(cap, WCS, 'Exception'), WCS, 'Format', 'application/vnd.ogc.se_xml')
        content = el(root, WCS, 'ContentMetadata')
        for m in models.values():
            cat = m.catalog()
            for v in m.ds.data_vars:
                for zi in range(m.ds.sizes['depth']): brief(content, m, v, zi, catalog=cat)
        if p.get('SECTION', '/') != '/':
            name = p['SECTION'].split('/')[-1]
            if p['SECTION'] not in [f'/WCS_Capabilities/{n}' for n in ('Service', 'Capability', 'ContentMetadata')]: raise ServiceError('InvalidParameterValue', 'Unsupported SECTION.')
            root = root.find(f'{{{WCS}}}{name}')
        return xml(root)
    identifiers = required(p, 'COVERAGE').split(',')
    if len(identifiers) > 64: raise ServiceError('InvalidParameterValue', 'Describe at most 64 coverages.')
    if op == 'DescribeCoverage':
        if len(identifiers) > 16 or sum(layer(models, identity, True)[0].ds.sizes['time'] for identity in identifiers) > 200_000:
            raise ServiceError('OperationNotSupported', 'Coverage description exceeds the metadata budget; request fewer coverages.')
        root = ET.Element(f'{{{WCS}}}CoverageDescription', version='1.0.0')
        for identifier in identifiers: brief(root, *layer(models, identifier, True), full=True)
        return xml(root)
    if op != 'GetCoverage': raise ServiceError('OperationNotSupported', 'Unsupported WCS operation.')
    if len(identifiers) != 1: raise ServiceError('InvalidParameterValue', 'GetCoverage requires one coverage.')
    m, variable, zi = layer(models, identifiers[0], True)
    if required(p, 'FORMAT') != 'NetCDF': raise ServiceError('InvalidParameterValue', 'Supported coverage FORMAT is NetCDF.', 'FORMAT')
    if p.get('INTERPOLATION', 'none').lower() != 'none' or any(k in p for k in ('WIDTH', 'HEIGHT', 'DEPTH', 'RESX', 'RESY', 'RESZ')):
        raise ServiceError('InvalidParameterValue', 'This coverage advertises interpolation=none; omit resampling sizes/resolutions.')
    b = bounds(p)
    if p.get('RESPONSE_CRS', 'EPSG:4326') != 'EPSG:4326': raise ServiceError('InvalidCRS', 'Reprojection is not supported.')
    from .science import Model
    native = Model(m.id, m.ds.isel(depth=slice(zi, zi+1)), m.provenance)
    data = subset_netcdf(native, variable, time_index(m, p), b)
    return Response(data, media_type='application/x-netcdf', headers={'Content-Disposition': 'attachment; filename="ocean3d-coverage.nc"'})


def dispatch(request, service):
    from .api import MODELS, LOCK
    try:
        p = params(request)
        if required(p, 'SERVICE') != service: raise ServiceError('InvalidParameterValue', f'SERVICE must be {service}.')
        op = required(p, 'REQUEST'); version = '1.3.0' if service == 'WMS' else '1.0.0'
        if op != 'GetCapabilities' and required(p, 'VERSION') != version: raise ServiceError('InvalidParameterValue', f'Only version {version} is implemented.')
        endpoint = str(request.url).split('?')[0]
        with LOCK:
            if service == 'WCS': return wcs_request(MODELS, p, endpoint)
            if op == 'GetCapabilities': return wms_capabilities(MODELS, endpoint)
            if op in ('GetMap', 'GetFeatureInfo'): return map_request(MODELS, p, op == 'GetFeatureInfo')
            raise ServiceError('OperationNotSupported', 'Unsupported WMS operation.')
    except ValueError as exc:
        root = ET.Element(f'{{{OGC}}}ServiceExceptionReport', version='1.3.0' if service == 'WMS' else '1.2.0')
        attrs = {'code': getattr(exc, 'code', 'InvalidParameterValue')}
        if getattr(exc, 'locator', None): attrs['locator'] = exc.locator
        el(root, OGC, 'ServiceException', str(exc), **attrs)
        return xml(root, 400)


@router.get('/api/ogc/wms')
def wms(request: Request): return dispatch(request, 'WMS')


@router.get('/api/ogc/wcs')
def wcs(request: Request): return dispatch(request, 'WCS')
