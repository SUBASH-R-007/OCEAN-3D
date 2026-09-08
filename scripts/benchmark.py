"""Small-fixture benchmark; no implication about operational archive scale."""
import json,time,statistics,gzip
from backend.demo import build_demo
from backend.analysis import compare

model,profiles=build_demo()
result={'dataset':'synthetic demo-v1','source_shape':dict(model.ds.sizes),'repeats':5}
for name,call in [('volume_36',lambda:model.volume('temperature',2,36)),('profile_match',lambda:compare(model,profiles[0],'temperature'))]:
    times=[]
    for _ in range(5):
        start=time.perf_counter();output=call();times.append((time.perf_counter()-start)*1000)
    encoded=json.dumps(output,separators=(',',':'),allow_nan=False).encode()
    result[name]={'median_ms':round(statistics.median(times),2),'max_ms':round(max(times),2),'json_bytes':len(encoded),'gzip_bytes':len(gzip.compress(encoded))}
print(json.dumps(result,indent=2))
