"""Acquire a bounded ETOPO 2022 numeric GeoTIFF, then build a terrain mesh packet.

Requires Pillow only for this offline data preparation, not the running API.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import subprocess
from urllib.parse import urlencode
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'data/geography'
BASE = 'https://gis.ngdc.noaa.gov/arcgis/rest/services/DEM_mosaics/DEM_all/ImageServer/exportImage'
PARAMS = dict(bbox='76,3,99,25', bboxSR='4326', size='230,220', imageSR='4326',
              format='tiff', pixelType='F32', interpolation='RSP_NearestNeighbor', compression='None',
              renderingRule=json.dumps({'rasterFunction': 'none'}),
              mosaicRule=json.dumps({'where': "Name='ETOPO_2022_v1_15s_surface_elev'"}), f='image')
URL = BASE + '?' + urlencode(PARAMS)


def build(path):
    with Image.open(path) as im:
        if im.format != 'TIFF' or im.mode != 'F' or im.size != (230, 220):
            raise ValueError('Expected numeric 230×220 float elevation raster, not a shaded image.')
        if tuple(im.tag_v2[33550]) != (0.1, 0.1, 0.0) or tuple(im.tag_v2[33922]) != (0.0, 0.0, 0.0, 76.0, 25.0, 0.0):
            raise ValueError('Unexpected GeoTIFF grid transform.')
        keys = im.tag_v2[34735]
        entries = {keys[i]: keys[i+3] for i in range(4, len(keys), 4)}
        if entries.get(2048) != 4326 or entries.get(1025) != 1:
            raise ValueError('Expected WGS84 pixel-is-area coordinates.')
        pixels = list(im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata())
    # GeoTIFF rows run north to south; application axes ascend south to north.
    elevation = [pixels[(219-y)*230+x] for y in range(220) for x in range(230)]
    if not all(math.isfinite(v) and -12000 < v < 10000 for v in elevation):
        raise ValueError('Unexpected missing or out-of-range elevation.')
    return dict(longitude=[round(76.05+x*.1, 6) for x in range(230)],
                latitude=[round(3.05+y*.1, 6) for y in range(220)],
                elevation=elevation,
                provenance=dict(title='NOAA ETOPO 2022 · ice surface elevation',
                    source_url=URL, metadata_url='https://www.ncei.noaa.gov/products/etopo-global-relief-model',
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    resolution='0.1° display extract from the 15 arc-second source; server nearest-neighbour sampling',
                    license='CC0-1.0; NOAA NCEI; DOI 10.25921/fd45-gt74',
                    warning='Geographic context only, not navigational bathymetry or the INCOIS model wet-cell mask.'))


def main():
    FOLDER.mkdir(parents=True, exist_ok=True)
    path = FOLDER / 'etopo-bay.tif'
    if not path.is_file():
        part = path.with_suffix('.part')
        subprocess.run(['curl.exe', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
                        '--max-time', '45', '--max-filesize', '3000000', '--silent', '--show-error',
                        URL, '--output', str(part)], check=True)
        build(part)
        part.replace(path)
    data = build(path)
    target = ROOT / 'web/public/geography/bay-relief.json'
    target.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    (FOLDER / 'provenance.json').write_text(json.dumps(data['provenance'], indent=2), encoding='utf-8')
    print(f'NOAA relief: {len(data["elevation"])} numeric elevations; {target.stat().st_size} bytes; '+data['provenance']['sha256'])


if __name__ == '__main__':
    main()
