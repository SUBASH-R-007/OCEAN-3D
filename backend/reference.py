"""Load the optional reproducible real case; never manufacture it when absent."""
from pathlib import Path
import json
import xarray as xr
from .science import Model, normalize, file_hash


def load_reference():
    folder=Path(__file__).resolve().parents[1]/'data'/'reference'
    if not (folder/'case.json').is_file():
        return None
    info=json.loads((folder/'case.json').read_text(encoding='utf-8'))
    path=folder/'model.nc'
    if file_hash(path)!=info['provenance']['sha256']:
        raise ValueError('Reference model checksum differs from its manifest.')
    with xr.open_dataset(path) as source:
        ds=normalize(source).load()
    return Model(info['id'],ds,info['provenance']),info['profiles']
