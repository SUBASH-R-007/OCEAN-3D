"""One bounded local burst to check admission and health; not a load certification."""
import asyncio
import json
import os
from pathlib import Path
import time
import httpx


async def main():
    headers={'Authorization':'Bearer '+os.environ['OCEAN_API_TOKEN']} if os.environ.get('OCEAN_API_TOKEN') else {}
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000',headers=headers,timeout=60) as client:
        results=[];health=[]
        async def request(i):
            query={'model':'scale-indian','variable':'temperature','index':i,'resolution':36,'maximum_depth':500,'bbox':'80,5,90,20'}
            start=time.perf_counter();response=await client.get('/api/volume.bin',params=query)
            assert response.status_code in (200,503),response.text[:200]
            if response.status_code==200: assert response.content[:4]==b'OCV1'
            else: assert response.headers.get('Retry-After')=='2'
            results.append({'index':i,'status':response.status_code,'seconds':time.perf_counter()-start,'query':query})
        async def health_check():
            for _ in range(8):
                start=time.perf_counter();r=await client.get('/api/health');assert r.status_code==200
                health.append(time.perf_counter()-start)
                await asyncio.sleep(.05)
        await asyncio.gather(*(request(i) for i in range(12)),health_check())
        retries=0
        for item in results:
            if item['status']==503:
                r=await client.get('/api/volume.bin',params=item['query']);assert r.status_code==200
                retries+=1
        result={'scope':'12 concurrent loopback requests in one burst, then sequential retry of capacity rejections',
                'initial_statuses':{str(status):sum(x['status']==status for x in results) for status in (200,503)},
                'successful_retries':retries,'health_seconds':health,'max_health_seconds':max(health),
                'runtime':(await client.get('/api/runtime')).json()}
        path=Path('docs/benchmarks/capacity-2026-09-07.json');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__': asyncio.run(main())
