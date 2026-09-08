"""Reproducible SYNTHETIC disk-archive benchmark, not an operational forecast test.

Prepare and measure in separate processes so generation does not contaminate RSS.
Default: 24 times x 64 depths x 512 x 512 = 1.5 GiB scalar field, six NetCDF files.
"""
import argparse
import ctypes
import gzip
import json
import os
from pathlib import Path
import statistics
import sys
import time
import numpy as np
from netCDF4 import Dataset
from backend.archive import load_archives
from backend.transport import encode_volume
from scripts.mount_archive import create_manifest


def peak_rss():
    if os.name=='nt':
        class Counters(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('peak','working','poolPeak','pool','nonPoolPeak','nonPool','page','pagePeak')]
        counters=Counters();counters.cb=ctypes.sizeof(counters)
        kernel=ctypes.windll.kernel32;kernel.GetCurrentProcess.restype=ctypes.c_void_p
        fn=ctypes.windll.psapi.GetProcessMemoryInfo
        fn.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
        if not fn(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb): raise OSError('Memory measurement failed.')
        return int(counters.peak)
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)


def prepare(root):
    root.mkdir(parents=True,exist_ok=True)
    manifest=root/'archive.json'
    if manifest.exists(): raise ValueError('Benchmark archive exists; run measurement or choose a fresh directory.')
    x=np.linspace(60,100,512);y=np.linspace(-10,30,512);z=np.linspace(0,4000,64)
    xx,yy=np.meshgrid(x,y);base=28+.04*xx-.09*yy;wet=xx >= 70+np.maximum(yy,0)*.22
    paths=[]
    for part in range(6):
        path=root/f'synthetic-part-{part:02}.nc'
        if path.exists(): raise ValueError(f'Refusing to overwrite {path.name}')
        with Dataset(path,'w',format='NETCDF4') as ds:
            ds.synthetic='true';ds.Conventions='CF-1.12';ds.title='Synthetic affine archive for scaling verification'
            for key,size in [('time',4),('depth',64),('latitude',512),('longitude',512)]: ds.createDimension(key,size)
            for key,values in [('time',np.arange(part*4,part*4+4)),('depth',z),('latitude',y),('longitude',x)]:
                c=ds.createVariable(key,'f8',(key,));c[:]=values
            ds['time'].units='hours since 2025-01-01 00:00:00';ds['time'].calendar='standard'
            ds['depth'].units='m';ds['depth'].positive='down'
            ds['longitude'].units='degrees_east';ds['latitude'].units='degrees_north'
            v=ds.createVariable('thetao','f4',('time','depth','latitude','longitude'),zlib=True,complevel=1,shuffle=True,chunksizes=(1,8,64,64),fill_value=np.float32(-9999))
            v.units='degree_Celsius';v.standard_name='sea_water_potential_temperature'
            for local in range(4):
                for zi in range(0,64,8):
                    block=base[None,:,:]-.005*z[zi:zi+8,None,None]+.02*(part*4+local)
                    v[local,zi:zi+8]=np.where(wet[None,:,:],block,-9999).astype('float32')
        paths.append(path)
        print(f'Prepared {part+1}/6 synthetic files',flush=True)
    create_manifest(manifest,'scale-indian','Synthetic Indian Ocean · 1.5 GiB scale test',paths,'Generated affine scaling fixture; not ocean observations')
    print(manifest)


def measure(root):
    started=time.perf_counter();model=load_archives(root/'archive.json')[0]
    registered=time.perf_counter()-started
    results=[]
    try:
        for region in (None,[80,5,90,20]):
            timings=[]
            for _ in range(3):
                start=time.perf_counter();frame=model.volume('temperature',12,64,500,region)
                timings.append(time.perf_counter()-start)
            binary=encode_volume(frame);text=json.dumps(frame,separators=(',',':'),allow_nan=False).encode()
            z,y,x=np.meshgrid(frame['axes']['depth'],frame['axes']['latitude'],frame['axes']['longitude'],indexing='ij')
            expected=28+.04*x-.09*y-.005*z+.02*12
            actual=np.array(frame['values'],float).reshape(z.shape);valid=np.isfinite(actual)
            error=float(np.max(np.abs(actual[valid]-expected[valid])))
            assert error < 2e-5
            results.append({'bbox':frame['bbox'],'display_shape':frame['dimensions'],'sampling':frame['sampling'],
                            'seconds':timings,'median_seconds':statistics.median(timings),'json_bytes':len(text),'binary_bytes':len(binary),
                            'json_gzip_bytes':len(gzip.compress(text)),'binary_gzip_bytes':len(gzip.compress(binary)),
                            'max_affine_error':error,'valid_cells':frame['valid_cells']})
        report={'synthetic':True,'source_shape':dict(model.ds.sizes),'scalar_logical_bytes':int(model.ds.temperature.nbytes),
                'source_file_bytes':model.provenance['source_bytes'],'files':len(model.provenance['files']),
                'archive_sha256':model.provenance['sha256'],'registration_seconds':registered,'process_peak_rss_bytes':peak_rss(),
                'results':results,'limitations':'Single process, one affine synthetic scalar, three sequential reads per region; timings include interpolation and JSON-list preparation. No global concurrent-user or GPU throughput claim; logical selected cells are not physical disk bytes.'}
        (root/'result.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
    finally: model.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path('tmp/scale-benchmark'))
    parser.add_argument('--prepare',action='store_true')
    args=parser.parse_args()
    (prepare if args.prepare else measure)(args.directory.resolve())
