"""One-shot idempotent inbox importer. Schedule on institutional infrastructure.

Files require a same-name .ready.json manifest, written after the producer closes
the data file: {"kind":"cf-profile","sha256":"..."}. No file is deleted/moved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import httpx


def ingest_inbox(inbox:Path, endpoint:str, token:str|None=None):
    inbox=inbox.resolve(); results=[]
    with httpx.Client(timeout=120, headers={'Authorization':f'Bearer {token}'} if token else {}) as client:
        for marker in sorted(inbox.glob('*.ready.json')):
            name=marker.name[:-len('.ready.json')]
            source=(inbox/name).resolve()
            if source.parent != inbox or not source.is_file():
                results.append({'file':name,'status':'invalid path'});continue
            receipt=inbox/(name+'.receipt.json')
            try:
                manifest=json.loads(marker.read_text(encoding='utf-8'))
                if source.stat().st_size>50*1024*1024: raise ValueError('File exceeds 50 MiB.')
                digest=hashlib.sha256(source.read_bytes()).hexdigest()
                if digest != manifest['sha256']: raise ValueError('Hash mismatch: producer has not finalized this file.')
                if receipt.exists():
                    previous=json.loads(receipt.read_text(encoding='utf-8'))
                    if previous.get('sha256')==digest and previous.get('requested_kind',previous.get('kind'))==manifest['kind']:
                        results.append({'file':name,'status':'already imported'});continue
                with source.open('rb') as stream:
                    response=client.post(endpoint.rstrip('/')+'/api/import',params={'kind':manifest['kind']},files={'file':(name,stream)},headers={'Idempotency-Key':digest+':'+manifest['kind']})
                response.raise_for_status(); result=response.json()
                result['requested_kind']=manifest['kind']
                pending=receipt.with_suffix('.pending')
                pending.write_text(json.dumps(result,indent=2),encoding='utf-8')
                pending.replace(receipt)
                results.append({'file':name,'status':'imported','id':result['id']})
            except (ValueError,KeyError,httpx.HTTPError,OSError) as exc:
                results.append({'file':name,'status':'error','detail':str(exc)})
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('inbox',type=Path);parser.add_argument('--endpoint',default='http://127.0.0.1:8000')
    args=parser.parse_args();results=ingest_inbox(args.inbox,args.endpoint,os.environ.get('OCEAN_API_TOKEN'))
    print(json.dumps(results,indent=2))
    raise SystemExit(1 if any(r['status'] in ('error','invalid path') for r in results) else 0)
