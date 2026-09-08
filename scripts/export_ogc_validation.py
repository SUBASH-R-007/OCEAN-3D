"""Write actual service responses for offline XML Schema validation."""
from fastapi.testclient import TestClient
from backend.api import app,ROOT

if __name__=='__main__':
    (ROOT/'tmp').mkdir(exist_ok=True)
    with TestClient(app) as client:
        for name,path,params in [
            ('wms-capabilities','wms',{'SERVICE':'WMS','REQUEST':'GetCapabilities'}),
            ('wcs-capabilities','wcs',{'SERVICE':'WCS','REQUEST':'GetCapabilities'}),
            ('wcs-description','wcs',{'SERVICE':'WCS','VERSION':'1.0.0','REQUEST':'DescribeCoverage','COVERAGE':'incois-bob:analyzed_temperature:0'}),
            ('wms-exception','wms',{'SERVICE':'WMS','VERSION':'1.3.0','REQUEST':'GetMap'})]:
            response=client.get('/api/ogc/'+path,params=params)
            assert response.status_code==(400 if 'exception' in name else 200),response.text
            (ROOT/'tmp'/(name+'.xml')).write_bytes(response.content)
    print('Exported four actual OGC responses.')
