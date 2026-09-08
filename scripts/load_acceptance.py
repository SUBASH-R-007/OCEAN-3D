"""Bounded scientific HTTP load measurement; no inferred production capacity."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import statistics
import threading
import time
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen


def percentile(values,fraction):
    if not values:return None
    values=sorted(values);position=(len(values)-1)*fraction
    low=int(position);high=min(low+1,len(values)-1)
    return values[low]+(values[high]-values[low])*(position-low)


def run(base_url,concurrencies=(1,2,4),seconds=10):
    if not 2<=seconds<=120 or not concurrencies or any(not 1<=c<=16 for c in concurrencies):raise ValueError('Use 2–120 seconds per stage and 1–16 clients.')
    headers={'Connection':'close'}
    if os.environ.get('OCEAN_API_TOKEN'):headers['Authorization']='Bearer '+os.environ['OCEAN_API_TOKEN']
    base=base_url.rstrip('/');stages=[];hashes={};guard=threading.Lock()
    def request(path):
        start=time.perf_counter()
        try:
            with urlopen(Request(base+path,headers=headers),timeout=30) as response:return response.status,response.read(),time.perf_counter()-start
        except HTTPError as exc:return exc.code,exc.read(),time.perf_counter()-start
        except (URLError,TimeoutError,OSError) as exc:return 0,str(exc).encode(),time.perf_counter()-start
    status,payload,_=request('/api/ready')
    if status!=200:raise RuntimeError('The target API is not ready.')
    ready=json.loads(payload)
    for clients in concurrencies:
        begin=time.perf_counter();deadline=begin+seconds;records=[];health=[]
        def worker(worker_id):
            number=worker_id
            while time.perf_counter()<deadline:
                index=number%3;number+=1
                path=f'/api/volume.bin?model=demo-bob&variable=temperature&index={index}&resolution=32'
                status,payload,elapsed=request(path);valid=status==200 and payload[:4]==b'OCV1'
                digest=hashlib.sha256(payload).hexdigest() if valid else None
                with guard:
                    if valid and index in hashes and hashes[index]!=digest:valid=False
                    elif valid:hashes[index]=digest
                    records.append(dict(status=status,seconds=elapsed,bytes=len(payload),valid=valid))
        with ThreadPoolExecutor(clients) as pool:
            futures=[pool.submit(worker,i) for i in range(clients)]
            while time.perf_counter()<deadline:
                status,payload,elapsed=request('/api/ready')
                health.append(dict(status=status,seconds=elapsed));time.sleep(min(1,max(0,deadline-time.perf_counter())))
            for future in futures:future.result()
        wall=time.perf_counter()-begin;latencies=[r['seconds'] for r in records if r['valid']]
        stages.append(dict(clients=clients,requested_seconds=seconds,actual_seconds=wall,requests=len(records),
            successful=len(latencies),rejected=sum(r['status']==503 for r in records),
            other_failures=sum(not r['valid'] and r['status']!=503 for r in records),
            success_per_second=len(latencies)/wall,latency_ms=dict(p50=1000*percentile(latencies,.5) if latencies else None,p95=1000*percentile(latencies,.95) if latencies else None),
            readiness=dict(probes=len(health),failures=sum(r['status']!=200 for r in health),max_latency_ms=1000*max(r['seconds'] for r in health))))
    return dict(base_url=base,created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        ready=ready,stages=stages,consistency_hashes=hashes,
        scope='Local/target HTTP measurement of three deterministic 32-resolution binary frames, including cache warming. Not a native-archive ingest, GPU benchmark, realistic user mix or sustained production-capacity certification.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base-url',default='http://127.0.0.1:3000')
    parser.add_argument('--seconds',type=int,default=10);parser.add_argument('--clients',default='1,2,4');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=run(args.base_url,tuple(map(int,args.clients.split(','))),args.seconds)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    raise SystemExit(1 if any(s['other_failures'] or s['readiness']['failures'] for s in result['stages']) else 0)
