"""Administrator-mounted immutable CF time archives. No arbitrary-path HTTP API."""
import hashlib
import json
from pathlib import Path
import re
import numpy as np
import xarray as xr
from .science import Model, open_bounded_model, file_hash


def load_archives(manifest_path, reserved=()):
    path = Path(manifest_path).resolve(strict=True)
    document = json.loads(path.read_text(encoding='utf-8'))
    if document.get('version') != 1 or not isinstance(document.get('archives'), list):
        raise ValueError('Archive manifest requires version=1 and archives[].')
    if len(document['archives']) > 32:
        raise ValueError('At most 32 mounted archives per process.')
    result, used = [], set(reserved)
    try:
        for entry in document['archives']:
            identity = entry.get('id', '')
            if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', identity) or identity in used:
                raise ValueError('Archive IDs must be unique and cannot replace another model.')
            if not isinstance(entry.get('title'), str) or not entry['title'].strip():
                raise ValueError('Archive title is required.')
            files = entry.get('files')
            if not isinstance(files, list) or not 1 <= len(files) <= 512:
                raise ValueError('An archive requires 1–512 explicitly listed files.')
            handles, normalized, evidence, seen = [], [], [], set()
            try:
                for item in files:
                    source = (path.parent / item['path']).resolve(strict=True)
                    # An explicit manifest is authorized configuration; paths must remain within its directory.
                    if not source.is_relative_to(path.parent) or source in seen or not source.is_file():
                        raise ValueError('Archive source must be a unique file inside the manifest directory.')
                    seen.add(source)
                    digest = file_hash(source)
                    if digest != item.get('sha256'):
                        raise ValueError(f'Archive checksum mismatch: {source.name}')
                    raw, ds = open_bounded_model(source)
                    handles.append(raw)
                    if normalized:
                        first = normalized[0]
                        if set(ds.data_vars) != set(first.data_vars):
                            raise ValueError('Archive files must have identical normalized variables.')
                        if any(not np.array_equal(ds[k].values, first[k].values) for k in ('depth','latitude','longitude')):
                            raise ValueError('Archive files must use identical spatial grids; no implicit regridding.')
                        if str(ds.attrs.get('synthetic', '')).lower() != str(first.attrs.get('synthetic', '')).lower():
                            raise ValueError('Archive files cannot mix synthetic and real provenance.')
                    normalized.append(ds)
                    evidence.append(dict(name=source.name, sha256=digest, bytes=source.stat().st_size))
                normalized.sort(key=lambda ds: ds.time.values[0])
                for previous, following in zip(normalized, normalized[1:]):
                    if previous.time.values[-1] >= following.time.values[0]:
                        raise ValueError('Archive timestamps overlap or repeat. Supply non-overlapping time files.')
                ds = xr.concat(normalized, dim='time', data_vars='minimal', coords='minimal', compat='equals', join='exact')
                if ds.sizes['time'] > 100_000:
                    raise ValueError('Archive exceeds the 100,000-frame catalog limit.')
                ds.set_close(lambda sources=tuple(handles): [source.close() for source in sources])
                fingerprint = hashlib.sha256(json.dumps(sorted(evidence, key=lambda x:(x['name'],x['sha256'])), sort_keys=True).encode()).hexdigest()
                provenance = dict(title=entry['title'], source=entry.get('source', 'Mounted CF time archive'),
                                  synthetic=str(ds.attrs.get('synthetic', '')).lower() == 'true', sha256=fingerprint,
                                  storage='lazy-netcdf-time-archive', files=evidence,
                                  source_bytes=sum(x['bytes'] for x in evidence), logical_bytes=int(ds.nbytes),
                                  warning='Administrator-mounted immutable snapshot. Time gaps and native masks remain explicit.')
                result.append(Model(identity, ds, provenance))
                used.add(identity)
            except Exception:
                for handle in handles:
                    handle.close()
                raise
        return result
    except Exception:
        for model in result:
            model.close()
        raise
