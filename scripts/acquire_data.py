"""Explicit upstream acquisition, not a network endpoint. Run --help for commands."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from datetime import datetime, timezone

def main():
    parser=argparse.ArgumentParser(description='Acquire bounded source-backed subsets. Supply your own authorized source/account.')
    sub=parser.add_subparsers(dest='command',required=True)
    argo=sub.add_parser('argo-file',help='Download one known HTTPS GDAC NetCDF profile, up to 50 MiB.')
    argo.add_argument('--url',required=True);argo.add_argument('--output',type=Path,required=True)
    cm=sub.add_parser('copernicus',help='Use the optional Copernicus Marine Toolbox; its own login/authentication applies.')
    cm.add_argument('--dataset-id',required=True);cm.add_argument('--variables',nargs='+',default=['thetao','so','uo','vo'])
    cm.add_argument('--bounds',nargs=4,type=float,metavar=('WEST','SOUTH','EAST','NORTH'),required=True)
    cm.add_argument('--start',required=True);cm.add_argument('--end',required=True);cm.add_argument('--max-depth',type=float,default=1000);cm.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Output exists; choose a new path to preserve the existing file.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.command=='argo-file':
        url=urlparse(args.url)
        if url.scheme!='https' or url.hostname not in ('data-argo.ifremer.fr','nrlgodae1.nrlmry.navy.mil') or not url.path.endswith('.nc'):
            parser.error('Supply an HTTPS .nc profile URL from an official Argo GDAC.')
        try:
            with urlopen(args.url,timeout=45) as r,args.output.open('xb') as f:
                total=0
                while block:=r.read(1024*1024):
                    total+=len(block)
                    if total>50*1024*1024:raise ValueError('File exceeds the 50 MiB acquisition limit.')
                    f.write(block)
            from backend.observations import parse_argo
            profiles=parse_argo(args.output)
            print(f'Validated {len(profiles)} Argo profiles. Confirm model time and region overlap before comparison.')
        except Exception:
            args.output.unlink(missing_ok=True);raise
        source=args.url
    else:
        west,south,east,north=args.bounds
        if not (-180<=west<east<=180 and -90<=south<north<=90) or args.max_depth<=0:parser.error('Invalid bounds or depth.')
        try:import copernicusmarine
        except ImportError:parser.error('Install the optional toolbox: pip install copernicusmarine. Authenticate using its documented workflow.')
        copernicusmarine.subset(dataset_id=args.dataset_id,variables=args.variables,minimum_longitude=west,maximum_longitude=east,minimum_latitude=south,maximum_latitude=north,minimum_depth=0,maximum_depth=args.max_depth,start_datetime=args.start,end_datetime=args.end,output_directory=str(args.output.parent),output_filename=args.output.name)
        source={'dataset_id':args.dataset_id,'variables':args.variables,'bounds':args.bounds,'start':args.start,'end':args.end,'max_depth':args.max_depth}
    h=hashlib.sha256()
    with args.output.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    manifest={'source':source,'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':h.hexdigest(),'synthetic':False}
    args.output.with_suffix('.source.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'Saved {args.output} and source manifest. Import through the local Data catalog.')

if __name__=='__main__':main()
