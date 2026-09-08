# Larger archives and bounded rendering

The scientific API can mount immutable, multi-file CF time archives without uploading them through the browser. xarray and Dask read selected data on demand. The existing React/VTK/FastAPI stack and pinned runtime dependencies are retained.

## Preparing and mounting an archive

Place files and the manifest in one administrator-owned directory. Files must have identical normalized spatial grids and variables, non-overlapping Gregorian times, compatible units and consistent synthetic/real provenance. Gaps between files remain gaps; interpolation applies the existing maximum-time-gap policy.

```powershell
python -m scripts.mount_archive --output C:/ocean/archive/archive.json --id operational-region --title "Regional model archive" C:/ocean/archive/day01.nc C:/ocean/archive/day02.nc
$env:OCEAN_ARCHIVE_MANIFEST = 'C:/ocean/archive/archive.json'
python -m backend.server
```

The command hashes and validates every listed file before finalizing the manifest. Startup verifies the hashes again. No source is accepted through an arbitrary-path HTTP parameter, and duplicate IDs, path escapes, mixed grids or overlapping timestamps fail registration. Files must remain immutable for the process lifetime; add a new manifest and restart for a new snapshot. This is not automatic live synchronization or a shared distributed registry.

For container deployment, the optional `compose.archives.yaml` mounts `OCEAN_ARCHIVE_DIR` read-only at `/app/archive`. Use it together with `compose.yaml`; the directory must contain `archive.json`. The local Docker engine remains unavailable, so container runtime acceptance is outstanding.

## Regional frames and precision

Explorer's Geographic region controls request west/south/east/north bounds inside the model domain. The source grid remains intact. Each output point uses its original bracketing source cells; any contributing missing corner invalidates it. Region selection concentrates the display samples without increasing native resolution. Profile markers and native export links follow the selected region. Model changes reset it.

The API-connected quality selector requests 36 or 64 samples per horizontal axis, with up to 96 depths in the upper-ocean window. Smaller native grids remain smaller unless a source explicitly supports display upsampling. The bundled demonstration retains its prebuilt frames; geographic subsetting requires the scientific API.

`GET /api/volume` retains JSON. `GET /api/volume.bin` accepts the same model, variable, index, resolution, maximum_depth and bbox parameters. The browser uses the binary route. Both return display data; native NetCDF exports retain native values and coordinates.

Binary layout:

1. Four ASCII bytes `OCV1`.
2. Unsigned little-endian 32-bit metadata length.
3. UTF-8 JSON metadata padded with spaces to a four-byte boundary.
4. Little-endian float32 scalars, x-fastest, then latitude, then positive-down depth. NaN represents missing data.

Metadata declares encoding version 1, `<f4`, `NaN`, dimensions, axes, valid count and source-sampling counts. The browser validates lengths, dimensions, axes, validity counts and encoding before rendering. Float32 transport follows the existing five-decimal display rounding; neither is used for model–observation collocation. Gzip is retained. Binary need not compress better for every source: the full-domain affine test compressed slightly better as JSON, while its regional binary response compressed better.

## Resource limits and deployment model

- 64 MiB server cache, counted by actual immutable encoded response bytes; at most 128 entries. Python object overhead and active computations are additional memory.
- 48 MiB browser cache budget using conservative decoded-array accounting; at most 24 entries. This is not a total browser/GPU memory ceiling.
- At most 6 admitted scientific requests per process by default (`OCEAN_MAX_ACTIVE`, 1–32). Excess requests return 503 with `Retry-After: 2`. `/api/runtime` exposes process-local cache and admission counters; the optional API token also protects it.
- Scientific reads remain serialized behind a process lock for conservative NetCDF access. Parsing runs off the event loop so health checks remain responsive. This limits concurrency rather than claiming parallel compute throughput.
- At most 32 archives, 512 explicitly listed files per archive, and 100,000 values per coordinate. Lazy Dask tasks use one time and at most 64 values on other dimensions. Physical compressed source chunks larger than 32 MiB are rejected before scientific reads.
- Analysis and export subset limits remain 8 million and 2 million native cells. Display frames are at most 393,216 cells. Large time sliders retain every frame but render at most five labels.
- WMS metadata has a 200,000 dimension-value budget; WCS capabilities permit 4,096 variable/depth coverages; descriptions permit 16 coverages and 200,000 timestamps per request. Oversized requests fail explicitly instead of silently omitting catalog entries.

The registry, caches, admission counters and import idempotency are process-local. The validated launcher requires one API worker for writable imports. `OCEAN_MODE=readonly` allows 1–8 workers serving an immutable published snapshot, with uploads and remote acquisition disabled. Never run a writer against files mounted by active readers. Multiple writable replicas still require a shared transactional registry and job service. Two read-only workers were verified locally; increasing workers also multiplies model/cache memory, and storage throughput, independent-user load, authentication, hardware budgets and failover must be tested on the target infrastructure. See [deployment modes and commands](DEPLOYMENT.md).

## Reproduce the executed benchmark

```powershell
python -m scripts.benchmark_scale --prepare
python -m scripts.benchmark_scale
```

Preparation generates six clearly synthetic, chunked NetCDF files under `tmp/scale-benchmark`, without overwriting existing files. Measurement runs separately from preparation. The 24 × 64 × 512 × 512 scalar field occupies 1,610,612,736 logical bytes (1.5 GiB); compressed source files total 107,712,333 bytes. The source fingerprint is `733dca2d6121e392e92e95e299b0165bf4f54c053f8b15aa9717d98481287fb2`.

Host: Windows, Intel Core i7-13650HX, 15.63 GiB physical memory, Python 3.11. Other local development services were present.

The initial executed run measured a 304 MiB process peak, a full-domain median of 0.307 s and regional median of 0.235 s for 64 × 64 × 96 frames. Each request selected 147,456 native cells out of a 16,777,216-cell source frame. These are logical source cells, not measured disk bytes: storage chunks may read additional cells. Regional float32 payload: 1,578,708 bytes versus 3,501,042 JSON bytes; gzip: 427,886 versus 497,807 bytes. Maximum affine-value error was below 0.000007°C. The machine-readable result is preserved in `docs/benchmarks/scale-2026-09-07.json`.

This is a single-process synthetic scalar benchmark, with three sequential uncached model reads per region. It establishes neither operational forecast skill nor global simultaneous-user/GPU throughput. Cache hits are not included in its latency figures. Further measurement must use representative INCOIS fields, chunk layouts and concurrency.

Implementation follows xarray's [Dask integration](https://docs.xarray.dev/en/stable/user-guide/dask.html) and [strict combination options](https://docs.xarray.dev/en/stable/generated/xarray.concat.html), with conservative per-file normalization and explicit grid/time checks. Dask's [chunking guidance](https://docs.dask.org/en/latest/array-chunks.html) explains why selected logical cells and physical I/O are different quantities.

The executed 12-request loopback burst admitted six requests and returned six 503 capacity responses; all six sequential retries succeeded. Eight concurrent health probes took 6–68 ms. This exercises backpressure and event-loop responsiveness rather than proving a production throughput target. Results: `docs/benchmarks/capacity-2026-09-07.json`; reproduce with the local scale archive mounted using `python -m scripts.probe_capacity`.

## Bounded HTTP load measurement, 8 September 2026

Run `python -m scripts.load_acceptance --base-url http://127.0.0.1:3000 --seconds 10 --clients 1,2,4 --output result.json`. The tool permits at most 16 clients and 120 seconds per stage. It measures three deterministic 32-resolution binary scalar frames, including cache warming, and checks that each frame's SHA-256 remains identical. Readiness is probed concurrently. It records 503 capacity responses separately from other errors.

| Clients | Successful requests / 10-second stage | Requests/s | p50 / p95 latency | Maximum readiness latency |
| --- | --- | --- | --- | --- |
| 1 | 588 | 58.8 | 12.3 / 32.8 ms | 30.7 ms |
| 2 | 922 | 92.0 | 18.3 / 40.0 ms | 211.5 ms |
| 4 | 1,624 | 162.1 | 20.9 / 50.5 ms | 213.3 ms |

All 3,134 requests succeeded with consistent frame hashes. There were no capacity rejections, other failures or failed readiness checks in this run. The ordinary Windows single-worker API served through Vite's same-origin development proxy; 18 models and 29 profiles were loaded after two public-source generations. [Raw measurements](benchmarks/http-load-2026-09-08.json).

This small, predominantly cached workload measures local HTTP behavior. It does not measure GPU rendering, native archive ingestion, sustained independent-user workloads, container/nginx throughput or production capacity. Agree acceptance thresholds before repeating the check on INCOIS hardware with its actual fields and request mix. The earlier uncached 1.5 GiB archive and admission-control probes address different paths; their results cannot be combined into a general capacity promise.
