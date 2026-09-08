"""Trusted deployment extension points; upload data never executes plugin code."""
import json
import re
from pathlib import Path
import numpy as np
from .science import VARIABLES


def register_variable(definition):
    """Register an already-canonical scalar from an administrator's JSON manifest."""
    required = {'id', 'label', 'unit', 'standard', 'aliases', 'range', 'unit_aliases', 'canonical_unit'}
    if set(definition) != required:
        raise ValueError('Variable plugin requires exactly: '+', '.join(sorted(required)))
    d = dict(definition); key = d.pop('id')
    if not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', key) or key in VARIABLES:
        raise ValueError('Variable plugin ID is invalid or already registered.')
    for name in ('label', 'unit', 'canonical_unit'):
        if not isinstance(d[name], str) or not d[name].strip() or len(d[name]) > 200:
            raise ValueError(f'Invalid variable {name}.')
    if d['standard'] is not None and (not isinstance(d['standard'],str) or not re.fullmatch(r'[a-z][a-z0-9_]*', d['standard'])):
        raise ValueError('standard must be a reviewed CF identifier or null for a source-specific quantity.')
    if not isinstance(d['range'], list) or len(d['range']) != 2 or not np.isfinite(d['range']).all() or d['range'][0] >= d['range'][1]:
        raise ValueError('Variable range must be two finite increasing values.')
    for name in ('aliases', 'unit_aliases'):
        if not isinstance(d[name], list) or not d[name] or not all(isinstance(v, str) and v.strip() for v in d[name]):
            raise ValueError(f'{name} must contain nonempty strings.')
    names={v.lower() for v in [key,*d['aliases']]}
    for existing,meta in VARIABLES.items():
        if (d['standard'] is not None and d['standard'] == meta['standard']) or names & {v.lower() for v in [existing,*meta['aliases']]}:
            raise ValueError('Variable plugin conflicts with an existing name or alias.')
    # A canonical definition must recognize its own exported name and unit,
    # even when a pack only lists additional source spellings as aliases.
    d['aliases'] = list(dict.fromkeys([key, *d['aliases']]))
    d['unit_aliases'] = list(dict.fromkeys(u.lower().replace(' ', '') for u in [d['canonical_unit'], *d['unit_aliases']]))
    d['plugin'] = True
    VARIABLES[key] = d
    return key


def load_variable_plugins(path):
    definitions = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(definitions, list) or len(definitions) > 64:
        raise ValueError('Variable manifest must contain at most 64 definitions.')
    added = []
    try:
        for definition in definitions: added.append(register_variable(definition))
    except Exception:
        for key in added: VARIABLES.pop(key)
        raise
    return added


ADAPTER_METADATA = {
    'model': {'label':'Model · CF NetCDF','container':'netcdf'},
    'argo': {'label':'Argo · GDAC NetCDF','container':'netcdf'},
    'cf-profile': {'label':'Glider / CTD / BGC · CF profiles','container':'netcdf'},
    'imos-glider': {'label':'IMOS glider · native profiles','container':'netcdf'},
    'cchdo-ctd': {'label':'CCHDO CTD · native profiles','container':'netcdf'},
    'csv': {'label':'Observations · delimited text','container':'text'},
    'tsv': {'label':'Observations · TSV','container':'text'},
    'txt': {'label':'Observations · ASCII / text','container':'text'},
}
ADAPTER_DETECTORS = {}
MODEL_ADAPTERS = {}
SENSORS = {}
PRODUCTS = {}
EXTENSIONS = {}


def register_observation_adapter(kind, parser, *, container='text', label=None, detector=None):
    """Call from trusted deployment code before serving. No HTTP plugin upload."""
    from .observations import ADAPTERS
    if not isinstance(kind,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', kind) or kind in ADAPTERS or kind in MODEL_ADAPTERS or kind in ('model','auto') or not callable(parser):
        raise ValueError('Invalid or duplicate adapter registration.')
    if container not in ('text','netcdf') or (detector is not None and not callable(detector)):
        raise ValueError('Adapter requires a text/netcdf container and an optional callable metadata detector.')
    if label is not None and (not isinstance(label,str) or not label.strip() or len(label)>160):
        raise ValueError('Adapter label must be nonempty and at most 160 characters.')
    ADAPTERS[kind] = parser
    ADAPTER_METADATA[kind] = {'label':label or kind,'container':container}
    if detector: ADAPTER_DETECTORS[kind] = detector
    return kind


def register_model_adapter(kind, parser, *, label, detector):
    """Trusted parser(path) -> (open xarray.Dataset, provenance dict). Core normalizes it."""
    register_observation_adapter(kind,parser,container='netcdf',label=label,detector=detector)
    from .observations import ADAPTERS
    MODEL_ADAPTERS[kind]=ADAPTERS.pop(kind)
    ADAPTER_METADATA[kind]['category']='model'
    return kind


def register_sensor(definition):
    required={'id','label','geometry','description'}
    if not isinstance(definition,dict) or set(definition)!=required:
        raise ValueError('Sensor requires id, label, geometry and description.')
    key=definition['id']
    if not isinstance(key,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,31}',key) or key in SENSORS:
        raise ValueError('Invalid or duplicate sensor ID.')
    if definition['geometry'] not in ('profile','time-series','surface-current'):
        raise ValueError('Unsupported sensor geometry; provide a reviewed renderer before adding a new geometry.')
    if any(not isinstance(definition[n],str) or not 0<len(definition[n])<=1000 for n in ('label','description')):
        raise ValueError('Sensor label and description must be bounded text.')
    SENSORS[key]=dict(definition)
    return key


def register_product(definition):
    required={'id','label','kind','version','outputs','method','limitations'}
    if not isinstance(definition,dict) or set(definition)!=required:
        raise ValueError('Product requires id, label, kind, version, outputs, method and limitations.')
    key=definition['id']
    if not isinstance(key,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',key) or key in PRODUCTS:
        raise ValueError('Invalid or duplicate product ID.')
    if definition['kind'] not in ('derived','machine-learning'):
        raise ValueError('Product kind must be derived or machine-learning.')
    for name in ('label','version','method','limitations'):
        if not isinstance(definition[name],str) or not 0<len(definition[name])<=2000:
            raise ValueError('Product metadata must be bounded nonempty text.')
    outputs=definition['outputs']
    if not isinstance(outputs,list) or not outputs or len(outputs)>64 or not all(isinstance(k,str) and k in VARIABLES for k in outputs) or len(set(outputs))!=len(outputs):
        raise ValueError('Product outputs must be distinct registered variables.')
    PRODUCTS[key]=dict(definition,outputs=list(outputs))
    return key


def registry_snapshot():
    from copy import deepcopy
    from .observations import ADAPTERS
    registries=(VARIABLES,ADAPTERS,ADAPTER_METADATA,ADAPTER_DETECTORS,MODEL_ADAPTERS,SENSORS,PRODUCTS,EXTENSIONS)
    return [(registry,deepcopy(registry)) for registry in registries]


def restore_registries(snapshot):
    for registry,contents in snapshot:
        registry.clear();registry.update(contents)


def load_extension_plugins(modules):
    """Versioned administrator modules. A failed pack rolls back every registry."""
    import importlib
    names=[n.strip() for n in modules.split(',') if n.strip()]
    if len(names)>16 or len(set(names))!=len(names) or any(not re.fullmatch(r'[A-Za-z_]\w*(\.[A-Za-z_]\w*)*',n) for n in names):
        raise ValueError('Extension modules must be at most 16 distinct installed Python module names.')
    snapshot=registry_snapshot()
    try:
        for name in names:
            module=importlib.import_module(name)
            meta=getattr(module,'PLUGIN',None)
            if not isinstance(meta,dict) or set(meta)!={'api_version','id','version','label'} or meta['api_version']!=1:
                raise ValueError('Extension PLUGIN metadata must declare API version 1, id, version and label.')
            if any(not isinstance(meta[n],str) or not 0<len(meta[n])<=160 for n in ('id','version','label')) or meta['id'] in EXTENSIONS:
                raise ValueError('Invalid or duplicate extension metadata.')
            if not callable(getattr(module,'register',None)): raise ValueError('Extension must expose register().')
            before=set(ADAPTER_METADATA)
            module.register()
            for kind in set(ADAPTER_METADATA)-before:
                ADAPTER_METADATA[kind]['plugin']={'id':meta['id'],'version':meta['version']}
            EXTENSIONS[meta['id']]={**meta,'module':name}
    except Exception:
        restore_registries(snapshot);raise
    return snapshot


def load_adapter_plugins(modules):
    """Administrator-listed installed modules expose register(); never supplied by an upload."""
    import importlib
    from .observations import ADAPTERS
    names=[name.strip() for name in modules.split(',') if name.strip()]
    if len(names)>16 or any(not re.fullmatch(r'[A-Za-z_]\w*(\.[A-Za-z_]\w*)*',name) for name in names):
        raise ValueError('OCEAN_ADAPTER_MODULES must list at most 16 installed Python module names.')
    before=set(ADAPTERS)
    try:
        for name in names: importlib.import_module(name).register()
    except Exception:
        unregister_adapters(set(ADAPTERS)-before)
        raise
    return list(set(ADAPTERS)-before)


def unregister_adapters(kinds):
    from .observations import ADAPTERS
    for kind in kinds:
        ADAPTERS.pop(kind,None); ADAPTER_METADATA.pop(kind,None); ADAPTER_DETECTORS.pop(kind,None)
