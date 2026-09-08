"""Validate generated responses with official, locally cached OGC XSDs.

Requires lxml for validation only. --fetch uses curl with normal TLS verification
and downloads schema dependencies only from OGC/W3C official schema hosts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import urljoin, urlsplit
from lxml import etree as ET

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'data/schemas/ogc'
START=['https://schemas.opengis.net/wms/1.3.0/capabilities_1_3_0.xsd','https://schemas.opengis.net/wms/1.3.0/exceptions_1_3_0.xsd','https://schemas.opengis.net/wcs/1.0.0/wcsAll.xsd']


def canonical(url):
    if url.startswith('http://'):url='https://'+url[7:]
    p=urlsplit(url)
    if p.scheme!='https' or p.netloc not in ('schemas.opengis.net','www.w3.org') or '..' in p.path.split('/'):
        raise ValueError('Unapproved schema dependency: '+url)
    return url


def local(url):
    p=urlsplit(canonical(url));return CACHE/p.netloc/p.path.lstrip('/')


def fetch():
    seen=set();queue=list(START);manifest=[]
    while queue:
        url=canonical(queue.pop())
        if url in seen:continue
        seen.add(url);path=local(url);path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():subprocess.run(['curl.exe','-fLsS','--max-time','30',url,'-o',str(path)],check=True)
        data=path.read_bytes();doc=ET.fromstring(data)
        manifest.append({'url':url,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
        for node in doc:
            if node.tag in ('{http://www.w3.org/2001/XMLSchema}include','{http://www.w3.org/2001/XMLSchema}import') and node.get('schemaLocation'):
                queue.append(urljoin(url,node.get('schemaLocation')))
    (CACHE/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'Cached {len(seen)} official schemas.')


class Resolver(ET.Resolver):
    def resolve(self,url,public_id,context):
        if url.startswith(('http://','https://')):return self.resolve_filename(str(local(url)),context)
        return None


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fetch',action='store_true');args=p.parse_args()
    if args.fetch:fetch()
    parser=ET.XMLParser(no_network=True);parser.resolvers.add(Resolver())
    wms=ET.XMLSchema(ET.parse(str(local(START[0])),parser));wcs=ET.XMLSchema(ET.parse(str(local(START[2])),parser));error=ET.XMLSchema(ET.parse(str(local(START[1])),parser))
    for name,schema in [('wms-capabilities',wms),('wcs-capabilities',wcs),('wcs-description',wcs),('wms-exception',error)]:
        doc=ET.parse(str(ROOT/'tmp'/(name+'.xml')),parser);schema.assertValid(doc);print(name+': official XSD passed')
