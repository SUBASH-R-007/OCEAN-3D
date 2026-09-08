"""Reproduce a bounded public INCOIS ERDDAP snapshot; HTTPS verification stays on."""
import sys,json,subprocess,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import xarray as xr
from backend.incois import DATASET_ID,INFO_URL,REPORT_URL,convert,support_summary
from backend.science import file_hash

SLICE='[(2026-05-15T00:00:00Z):1:(2026-07-15T00:00:00Z)][(5):1:(2000)][(5.5):1:(22.5)][(79.5):1:(95.5)]'
FIELDS=['T_ANALYZED','S_ANALYZED','T_STDEV','T_RMSE','T_ROIOBS','T_BOXOBS','S_ROIOBS','S_BOXOBS']
SOURCE='https://erddap.incois.gov.in/erddap/griddap/'+DATASET_ID+'.nc?'+quote(','.join(v+SLICE for v in FIELDS),safe=',:')

def acquire(url,path,limit=5*1024*1024):
    if path.exists(): return
    curl=shutil.which('curl.exe' if sys.platform=='win32' else 'curl')
    if not curl: raise RuntimeError('curl is required for verified HTTPS downloads.')
    pending=path.with_suffix(path.suffix+'.part')
    try:
        subprocess.run([curl,'--fail','--location','--silent','--show-error','--proto','=https','--proto-redir','=https',
                        '--max-time','45','--max-filesize',str(limit),'--output',str(pending),url],check=True,timeout=50)
        if pending.stat().st_size>limit: raise ValueError('INCOIS source exceeds the bounded download.')
        if path.suffix=='.nc':
            with xr.open_dataset(pending) as ds: convert(ds)
        else: json.loads(pending.read_text(encoding='utf-8'))
        pending.replace(path)
    finally:
        if pending.exists(): pending.unlink()

def main():
    folder=ROOT/'data'/'incois';folder.mkdir(parents=True,exist_ok=True)
    acquire(SOURCE,folder/'source.nc')
    acquire(INFO_URL.replace('index.html','index.json'),folder/'metadata.json')
    with xr.open_dataset(folder/'source.nc') as raw:
        ds=convert(raw);ds.to_netcdf(folder/'model.nc')
        support=support_summary(raw);license_text=raw.attrs.get('license','');history=raw.attrs.get('history','')
    provenance=dict(title=ds.attrs['title'],source='INCOIS Argo monthly objective analysis · official INCOIS ERDDAP',
                    synthetic=False,provider='INCOIS',product_type='monthly_objective_analysis',dataset_id=DATASET_ID,display_upsampling=True,
                    source_url=SOURCE,metadata_url=INFO_URL,documentation_url=REPORT_URL,
                    sha256=file_hash(folder/'model.nc'),source_sha256=file_hash(folder/'source.nc'),
                    retrieved_at=datetime.now(timezone.utc).isoformat(),license=license_text,source_history=history,
                    warning='Monthly analyzed fields, not a live forecast. Source temperature does not declare potential versus in-situ convention; density diagnostics and temperature-profile comparisons are disabled for this product. Spread is within-analysis variability, not a confidence interval.',
                    spatial_resolution='1° × 1° native grid; 24 source depth levels',temporal_resolution='Monthly; date marks the month, not an instantaneous observation',
                    temperature_definition='As published; potential versus in-situ unspecified. Celsius interpreted from the INCOIS product report.',
                    transformations=['Native ERDDAP subset: May–July 2026, 79.5–95.5°E, 5.5–22.5°N, 5–2000 m; no source stride.',
                                     'Decode 9999 fill values; retain the source missing-cell mask.',
                                     'Keep analyzed temperature separate from potential temperature. Map explicitly identified practical salinity to the application convention.',
                                     'Retain source spread and counts. Source salinity-count PSU/standard-name metadata is erroneous; counts are reported as counts, never salinity.'],
                    support_by_time=support)
    info=dict(id='incois-bob',provenance=provenance,profiles=[])
    (folder/'case.json').write_text(json.dumps(info,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(id=info['id'],shape=dict(ds.sizes),source_bytes=(folder/'source.nc').stat().st_size,support=support),indent=2))

if __name__=='__main__': main()
