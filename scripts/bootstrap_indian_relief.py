"""Numeric ETOPO 2022 context for the full INCOIS analysis domain."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,math,subprocess
from urllib.parse import urlencode
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
BASE='https://gis.ngdc.noaa.gov/arcgis/rest/services/DEM_mosaics/DEM_all/ImageServer/exportImage'
PARAMS=dict(bbox='30,-30,120,30',bboxSR='4326',size='360,240',imageSR='4326',format='tiff',pixelType='F32',interpolation='RSP_NearestNeighbor',compression='None',renderingRule=json.dumps({'rasterFunction':'none'}),mosaicRule=json.dumps({'where':"Name='ETOPO_2022_v1_15s_surface_elev'"}),f='image')
URL=BASE+'?'+urlencode(PARAMS)


def main():
    path=ROOT/'data/geography/etopo-indian.tif'
    if not path.exists():
        part=path.with_suffix('.part')
        subprocess.run(['curl.exe','--fail','--silent','--show-error','--proto','=https','--max-time','45','--max-filesize','4000000',URL,'-o',str(part)],check=True)
        part.replace(path)
    with Image.open(path) as im:
        if im.mode!='F' or im.size!=(360,240) or tuple(im.tag_v2[33550])!=(.25,.25,0) or tuple(im.tag_v2[33922])!=(0,0,0,30,30,0):raise ValueError('Unexpected NOAA raster georeferencing.')
        keys=im.tag_v2[34735];entries={keys[i]:keys[i+3] for i in range(4,len(keys),4)}
        if entries.get(2048)!=4326 or entries.get(1025)!=1:raise ValueError('Expected WGS84 pixel-is-area.')
        pixels=list(im.get_flattened_data())
    elevation=[pixels[(239-y)*360+x] for y in range(240) for x in range(360)]
    if not all(math.isfinite(v) and -12000<v<10000 for v in elevation):raise ValueError('Invalid ETOPO elevation.')
    packet=dict(longitude=[30.125+i*.25 for i in range(360)],latitude=[-29.875+i*.25 for i in range(240)],elevation=elevation,
      provenance=dict(title='NOAA ETOPO 2022 · Indian Ocean context',source_url=URL,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),retrieved_at=datetime.now(timezone.utc).isoformat(),resolution='0.25° display extract from 15 arc-second ETOPO 2022; nearest-neighbour sampling',license='CC0-1.0; NOAA NCEI; DOI 10.25921/fd45-gt74'))
    (ROOT/'web/public/geography/indian-relief.json').write_text(json.dumps(packet,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print('Indian Ocean relief',len(elevation),packet['provenance']['sha256'])


if __name__=='__main__':main()
