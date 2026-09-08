"""INCOIS tabledap profile selections. Raw and adjusted channels stay distinct."""
from datetime import datetime, timezone
from urllib.parse import quote
import hashlib
import json
import math
import gsw
from .incois_catalog import FOLDER, BASE, acquire, IO_LOCK, product_for
from .science import file_hash

FIELDS=['DATE_CREATION','DATE_UPDATE','PLATFORM_TYPE','JULD_LOCATION','PLATFORM_NUMBER','CYCLE_NUMBER','DIRECTION','time','JULD_QC','latitude','longitude'] + [k+s for k in ('PRES','TEMP','PSAL') for s in ('','_QC','_ADJUSTED','_ADJUSTED_QC')]


def observation_query(start,end,bbox=None,revision=None):
    product=product_for('Indian_ARGO_Floats',revision)
    def date(s):
        d=datetime.fromisoformat(s.replace('Z','+00:00'))
        if d.tzinfo is None: raise ValueError('UTC timestamps are required.')
        return d.astimezone(timezone.utc)
    a,b=date(start),date(end)
    if a>b or (b-a).total_seconds()>7*86400: raise ValueError('Choose a window of at most seven days.')
    if a<date(product['start']) or b>date(product['end']): raise ValueError('Time window exceeds the published observation archive.')
    query=','.join(FIELDS)+f'&time>={a.isoformat()}&time<={b.isoformat()}'
    if bbox is not None:
        if len(bbox)!=4 or not all(math.isfinite(x) for x in bbox) or not -180<=bbox[0]<bbox[2]<=180 or not -90<=bbox[1]<bbox[3]<=90:
            raise ValueError('Choose ordered geographic bounds in -180…180 longitude.')
        query+=f'&longitude>={bbox[0]}&longitude<={bbox[2]}&latitude>={bbox[1]}&latitude<={bbox[3]}'
    return BASE+'/tabledap/Indian_ARGO_Floats.json?'+quote(query,safe=',')


def parse_table(table):
    columns=table['columnNames']; groups={}
    def finite(v):return isinstance(v,(float,int)) and math.isfinite(v)
    def flag(v): return int(v) if str(v).strip().isdigit() and 0<=int(v)<=9 else 0
    for row in table['rows']:
        r=dict(zip(columns,row)); lon,lat=r['longitude'],r['latitude']
        if not finite(lon) or not finite(lat) or not -180<=lon<=180 or not -90<=lat<=90: continue
        # Preserve separate cycles/directions/timestamps, including multiple casts per float.
        key=':'.join(str(r[k]).strip() for k in ('PLATFORM_NUMBER','CYCLE_NUMBER','DIRECTION','time'))
        p=groups.setdefault(key,dict(id=key,float=str(r['PLATFORM_NUMBER']).strip(),cycle=r['CYCLE_NUMBER'],direction=r['DIRECTION'],time=r['time'],time_qc=flag(r['JULD_QC']),longitude=lon,latitude=lat,levels=[]))
        p['source_metadata']={k:r.get(k) for k in ('DATE_CREATION','DATE_UPDATE','PLATFORM_TYPE','JULD_LOCATION')}
        level={}
        for channel,suffix in (('raw',''),('adjusted','_ADJUSTED')):
            pres=r['PRES'+suffix]
            vals={k.lower():r[k+suffix] if finite(r[k+suffix]) else None for k in ('PRES','TEMP','PSAL')}
            flags={k.lower():flag(r[k+suffix+'_QC']) for k in ('PRES','TEMP','PSAL')}
            z=float(-gsw.z_from_p(pres,lat)) if finite(pres) and 0<=pres<=12000 else None
            level[channel]=dict(**vals,depth=z,qc=flags)
        p['levels'].append(level)
    return list(groups.values())


def observation_packet(start,end,bbox=None,revision=None):
    url=observation_query(start,end,bbox,revision)
    with IO_LOCK:
        # Tables share the bounded cache budget with grids.
        folder=FOLDER/'tables';folder.mkdir(exist_ok=True)
        files=sorted(folder.glob('*.json'),key=lambda p:p.stat().st_mtime)
        while len(files)>=8: files.pop(0).unlink()
        cache_key=url if not revision else url+'#'+revision
        path=acquire(url,folder/(hashlib.sha256(cache_key.encode()).hexdigest()+'.json'),16*1024*1024)
        table=json.loads(path.read_text(encoding='utf-8'))['table']
        return dict(schema='ocean3d-incois-observations-1',start=start,end=end,source_url=url,source_sha256=file_hash(path),
                    retrieved_at=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),source_rows=len(table['rows']),profiles=parse_table(table),
                    method='Published raw and adjusted channels kept separate; no silent fallback. GSW pressure-to-depth conversion uses profile latitude. Strict display requires QC 1 or 2 for time, pressure and the selected variable. Position QC and DATA_MODE are not exposed by this table. Temperature is in-situ ITS-90; no comparison to unspecified analyzed temperature.')
