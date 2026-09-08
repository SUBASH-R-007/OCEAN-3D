"""Bounded HTTP acceptance probe for a deployed Ocean3D service; standard library only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def check(base_url, expected_mode, expected_workers=1):
    base=base_url.rstrip('/')
    headers={'Connection':'close'}
    if os.environ.get('OCEAN_API_TOKEN'):
        headers['Authorization']='Bearer '+os.environ['OCEAN_API_TOKEN']
    def request(path, body=None):
        req=Request(base+path,data=body,headers=headers)
        try:
            with urlopen(req,timeout=30) as response:
                return response.status,response.read(),response.headers
        except HTTPError as exc:
            return exc.code,exc.read(),exc.headers
    def get(path):
        status,data,_=request(path)
        if status!=200: raise RuntimeError(f'{path} returned HTTP {status}.')
        return json.loads(data)
    deadline=time.monotonic()+60
    while True:
        try:
            ready=get('/api/ready')
            break
        except (RuntimeError,URLError):
            if time.monotonic()>=deadline: raise
            time.sleep(.5)
    assert ready['status']=='ready' and ready['mode']==expected_mode,ready
    assert get('/api/health')['mode']=='scientific-api'
    schema=get('/api/openapi.json')
    assert '/api/volume.bin' in schema['paths'] and '/api/ready' in schema['paths']
    catalog=get('/api/catalog')
    assert catalog['models'] and catalog['profiles']
    results=[]
    def sample(_):
        runtime=get('/api/runtime')['deployment']
        assert runtime['mode']==expected_mode and runtime['configured_workers']==expected_workers,runtime
        start=time.perf_counter()
        status,data,frame_headers=request('/api/volume.bin?model=demo-bob&variable=temperature&resolution=8')
        assert status==200 and data[:4]==b'OCV1',status
        return dict(worker_pid=runtime['worker_pid'],revision=runtime['startup_catalog_revision'],
                    frame_worker_pid=int(frame_headers['X-Ocean-Worker']),
                    frame_sha256=hashlib.sha256(data).hexdigest(),seconds=time.perf_counter()-start)
    with ThreadPoolExecutor(4) as pool:
        for _ in range(8):
            results.extend(pool.map(sample,range(4)))
            if (len({r['worker_pid'] for r in results})>=expected_workers and
                    len({r['frame_worker_pid'] for r in results})>=expected_workers): break
            time.sleep(.2)
    workers=sorted({r['worker_pid'] for r in results})
    assert len(workers)>=expected_workers,f'Only observed workers {workers}; expected at least {expected_workers}.'
    assert len({r['frame_worker_pid'] for r in results})>=expected_workers,'Did not sample a frame from every worker.'
    assert len({r['revision'] for r in results})==1,'Worker catalogs differ.'
    assert len({r['frame_sha256'] for r in results})==1,'The same requested frame differs across responses.'
    if expected_mode=='readonly':
        assert not ready['capabilities']['imports'] and not ready['capabilities']['upstream_acquisition']
        for path in ('/api/import/inspect','/api/import','/api/incois/open'):
            assert request(path,b'blocked-before-parsing')[0]==403,path
    return dict(base_url=base,mode=expected_mode,workers_observed=workers,
                models=ready['models'],profiles=ready['profiles'],probes=results,
                scope='Readiness, same-origin API contract, replica catalog/frame consistency and read-only mutation rejection; not a throughput benchmark.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8080')
    parser.add_argument('--mode',choices=('writable','readonly'),default='writable')
    parser.add_argument('--workers',type=int,choices=range(1,9),default=1)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=check(args.base_url,args.mode,args.workers)
    text=json.dumps(result,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding='utf-8')
    print(text)


if __name__=='__main__': main()
