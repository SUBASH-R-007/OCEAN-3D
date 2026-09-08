"""Create a verified administrator manifest for immutable local CF time files."""
import argparse
import json
from pathlib import Path
from backend.archive import load_archives
from backend.science import file_hash


def create_manifest(output, identity, title, files, source='Mounted CF time archive'):
    output=Path(output).resolve()
    if output.exists(): raise ValueError('Manifest already exists. Choose a new immutable manifest name.')
    records=[]
    for file in files:
        path=Path(file).resolve(strict=True)
        if not path.is_relative_to(output.parent): raise ValueError('All source files must be inside the manifest directory.')
        records.append({'path':path.relative_to(output.parent).as_posix(),'sha256':file_hash(path)})
    pending=output.with_suffix(output.suffix+'.pending')
    with pending.open('x',encoding='utf-8') as stream:
        json.dump({'version':1,'archives':[{'id':identity,'title':title,'source':source,'files':records}]},stream,indent=2)
    try:
        models=load_archives(pending)
        for model in models: model.close()
        if output.exists(): raise ValueError('Manifest appeared during validation; refusing replacement.')
        pending.rename(output)
    finally: pending.unlink(missing_ok=True)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--id',required=True)
    parser.add_argument('--title',required=True)
    parser.add_argument('--source',default='Mounted CF time archive')
    parser.add_argument('files',nargs='+',type=Path)
    args=parser.parse_args()
    print(create_manifest(args.output,args.id,args.title,args.files,args.source))
