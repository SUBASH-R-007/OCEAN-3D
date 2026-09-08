"""Ingest externally computed fields with explicit, versioned provenance; no code loading."""
import json
import re
from datetime import datetime, timezone
import xarray as xr
from ..plugins import PRODUCTS, register_model_adapter

PLUGIN={'api_version':1,'id':'derived-products','version':'1.0.0','label':'Derived and ML field ingestion'}


def read_product(path):
    raw=xr.open_dataset(path)
    try:
        key=raw.attrs.get('ocean3d_product_id')
        if key not in PRODUCTS: raise ValueError('This derived product is not registered by the administrator.')
        definition=PRODUCTS[key]
        if raw.attrs.get('ocean3d_product_version')!=definition['version']:
            raise ValueError('Product version differs from the installed definition; install the matching version before import.')
        encoded=raw.attrs.get('ocean3d_lineage','')
        if not isinstance(encoded,str) or len(encoded)>32_000: raise ValueError('Product lineage must be bounded JSON text.')
        try: lineage=json.loads(encoded)
        except (ValueError,TypeError) as exc: raise ValueError('Provide ocean3d_lineage JSON metadata.') from exc
        required={'generated_at','inputs','validation','limitations'}
        if definition['kind']=='machine-learning': required|={'artifact_sha256','training_data','inference_domain'}
        if not isinstance(lineage,dict) or set(lineage)!=required: raise ValueError('Product lineage fields must be exactly: '+', '.join(sorted(required)))
        for name in required-{'inputs'}:
            if not isinstance(lineage[name],str) or not 0<len(lineage[name])<=4000: raise ValueError(f'Invalid lineage {name}.')
        try:
            date=datetime.fromisoformat(lineage['generated_at'].replace('Z','+00:00'))
            if date.tzinfo is None: raise ValueError('Offset required')
        except ValueError as exc: raise ValueError('Product generation time requires an ISO timestamp with UTC offset.') from exc
        lineage['generated_at']=date.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
        inputs=lineage['inputs']
        if not isinstance(inputs,list) or not 1<=len(inputs)<=64: raise ValueError('List 1–64 input dataset identities and SHA-256 hashes.')
        seen=set()
        for source in inputs:
            if not isinstance(source,dict) or set(source)!={'id','sha256'} or not isinstance(source['id'],str) or not 0<len(source['id'])<=200 or source['id'] in seen:
                raise ValueError('Input source identities must be distinct nonempty strings.')
            seen.add(source['id'])
            if not isinstance(source['sha256'],str) or not re.fullmatch(r'[a-f0-9]{64}',source['sha256']): raise ValueError('Input sources require lowercase SHA-256 hashes.')
        if 'artifact_sha256' in lineage and not re.fullmatch(r'[a-f0-9]{64}',lineage['artifact_sha256']):
            raise ValueError('ML artifact requires a lowercase SHA-256 hash.')
        return raw,dict(source=definition['label'],product={**definition,'lineage':lineage},
            warning='Derived output, not an instrument observation. '+definition['limitations']+' '+lineage['validation'])
    except Exception:
        raw.close();raise


def register():
    register_model_adapter('derived-cf',read_product,label='Derived / ML product · CF NetCDF',
        detector=lambda meta:'ocean3d_product_id' in meta.get('attrs',{}))
