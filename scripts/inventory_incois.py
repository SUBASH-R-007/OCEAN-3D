"""Snapshot the complete public INCOIS ERDDAP catalogue and metadata."""
import concurrent.futures
import json
import subprocess
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.incois_catalog import acquire,BASE
FOLDER = ROOT / 'data/incois-catalog'


def fetch(row,refresh=False):
    if not re.fullmatch('[A-Za-z0-9_]+',row['Dataset ID']):raise ValueError('Unexpected source dataset identifier.')
    path = FOLDER / (row['Dataset ID'] + '.json')
    acquire(f'{BASE}/info/{row["Dataset ID"]}/index.json',path,2*1024*1024,refresh=refresh)
    table = json.loads(path.read_text(encoding='utf-8'))['table']
    dimensions = [r[:5] for r in table['rows'] if r[0] == 'dimension']
    ranges = [r[1:5] for r in table['rows'] if r[2] in ('actual_range', 'time_coverage_start', 'time_coverage_end')]
    return {'id': row['Dataset ID'], 'dimensions': dimensions, 'ranges': ranges}


def inventory(refresh=False):
    acquire(BASE+'/info/index.json?itemsPerPage=1000&page=1',FOLDER/'catalog-source.json',2*1024*1024,refresh=refresh)
    table = json.loads((FOLDER / 'catalog-source.json').read_text(encoding='utf-8'))['table']
    rows = [dict(zip(table['columnNames'], r)) for r in table['rows'] if r[-1] != 'allDatasets']
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda r:fetch(r,refresh), rows):
            print(json.dumps(result))


if __name__ == '__main__':inventory('--refresh' in sys.argv)
