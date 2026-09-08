# Ocean3D — ocean evidence workbench

A working SIH26067 regional ocean prototype: inspect a real 3D field, compare quality-approved observations, understand water-column physics, and preserve the evidence.

**8 September coverage expansion:** the INCOIS source library now covers all 16 products in the public ERDDAP catalogue: 86 gridded variables, 26,084 source time coordinates, four full Indian Ocean 3D analysis products and individual Argo observations. Ocean lab supports the full basin, Arabian Sea, Bay of Bengal, island regions and southern/equatorial Indian Ocean. Historical selections load on demand through the scientific API; source dates, units, quality flags, missing cells and hashes remain visible. [Exact coverage, source limits and operating instructions](docs/INCOIS_COVERAGE.md).

[Open the existing hosted demonstration](https://ocean3d-sih26067.kuttykoncepts1.chatgpt.site). It still contains the earlier release. The INCOIS update is local; uploading and public publishing await approval. The production review runs at http://127.0.0.1:3001/ while its helper is active. Self-hosting adds ingestion and scientific API exports.

## What is implemented

- **Ocean lab:** actual NOAA ETOPO 2022 terrain with layered INCOIS thermal surfaces, staggered cutaways, 3D probing, native-profile curtains, month-to-month isotherm depth change and a local-observation filter.
- **Instrument and portal extension:** native CF glider/profile collections, timestamp-ordered mission joins, administrator scalar plugins, repeatable inbox ingestion, WMS maps/queries and native WCS NetCDF coverages.
- **Versioned extension packs:** mooring time series, earth-referenced ADCP profiles and HF-radar total surface currents; plugin model readers and scalar variables; precomputed derived/ML fields with explicit version and lineage. Synthetic examples exercise each contract without claiming trained ML or live sensor feeds.
- **Learn:** four interactive lessons connected to the actual 3D Explorer, with interpretation questions and feedback.
- Native crossing brackets and support counts accompany each change; investigation exports retain the source evidence. [Novelty, methods and data provenance](docs/OCEAN_LAB_NOVELTY.md).
- Official INCOIS Argo monthly Bay of Bengal fields, May–July 2026: analyzed temperature, salinity, spread, native observation support and source hashes.
- Persistent VTK.js GPU volumes, cutaways, intersecting 3D sections, slices, lit masked isosurfaces, top/front cameras, palettes, opacity, time animation and vertical exaggeration.
- Natural Earth geography, observed profile-depth guides, selectable instruments and explicit timestamp freshness.
- Full-depth and upper-500-m views with independent source-grid scientific analysis.
- Geographic RK4 current streamlines with animated particles and physical-unit vectors. Fixed depth/frozen time are explicit; these are not forecast trajectories.
- TEOS-10 density mixed-layer depth, thermal departure, signed barrier-layer separation, N² and threshold sensitivity with gap-aware crossing brackets.
- Retrieved HYCOM/Argo historical case: 1,001 matched QC-1 levels; a second rejected real cast demonstrates missing adjusted-data handling.
- Native-grid 4D profile matching, strict/lenient QC, bias/MAE/RMSE, exclusions, transects and observation-distance coverage.
- Validated CF NetCDF, GDAC Argo and CSV/TSV imports with file hashes and restart persistence.
- Evidence JSON, paired CSV, native-grid CF-described NetCDF and schema-tested CoverageJSON exports.
- Four exploration journeys, responsive controls, saved views, view-state links and an extensive source-linked research dossier.

React + VTK.js + FastAPI/xarray were retained. Physical calculations use GSW/TEOS-10; no machine-learning forecast or invented confidence percentage is presented.

## Run locally on Windows

Python 3.11 and Node.js 22.13 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
cd web
npm ci
cd ..
.\start.ps1
```

Open `http://127.0.0.1:3000`. The script runs the API in a hidden helper and stops it when the frontend exits. Ports 3000 and 8000 must be free. The API reference is at `http://127.0.0.1:3000/api/docs` through the same-origin proxy.

Alternatively run these in separate terminals:

```powershell
# Repository root
.\.venv\Scripts\python.exe -m backend.server
# web directory
npm run dev:selfhost
```

## A four-minute SIH demonstration

Start in **Ocean lab**. Reveal the three temperature layers over the real basin, switch to Monthly change, and inspect the largest 20°C depth change. Select a point with the 3D Probe, inspect both native crossing brackets below the scene, then enable **Only pairs with local observations** to expose where source support is local. Export the investigation. Explain that monthly isotherm displacement is not water motion, and that the depth lens deliberately exaggerates shallow structure. [Detailed methodology](docs/OCEAN_LAB_NOVELTY.md).

Continue in **Explorer → INCOIS · Bay of Bengal** to rotate the volumetric field, move intersecting sections, switch May–July and inspect temperature spread. Distinguish the native 1° grid and 24 depths from display interpolation. These existing workflows remain:

1. **Water-column structure:** rotate, inspect the cutaway, change the isovalue, then explain the mixed-layer crossing bracket and threshold sensitivity.
2. **Current circulation:** inspect the animated streamlines and depth controls. State that the scene is frozen in time and has no vertical velocity.
3. **Real-data validation:** show the 1,001 matched levels, separate observation/model timestamps and source provenance. Switch to cast `2902394-290-0` to show exclusion of 511 bad adjusted-salinity levels.
4. **Reproduce the result:** export the evidence, inspect the catalog, and open Research & methods to explain the physical definitions and remaining integration work.

The real case is in the eastern equatorial Indian Ocean, south of the Bay of Bengal, on 1 September 2023. Temperature RMSE is 0.65527°C for this one cast and model subset. Assimilation independence is unknown; it is not an independent or general forecast-skill estimate. The separate Bay of Bengal eddy fixture is synthetic.

## Reproduce data and checks

Source files and provenance manifests are included under `data/reference` and `data/incois`. INCOIS temperature stays separate from potential temperature because its thermodynamic convention is unspecified. Density diagnostics and temperature matching remain available on compatible datasets. To reproduce the public snapshots and regenerate bundled cases:

```powershell
.\.venv\Scripts\python.exe -m scripts.bootstrap_reference
.\.venv\Scripts\python.exe -m scripts.bootstrap_incois
.\.venv\Scripts\python.exe -m scripts.export_thermal_atlas
.\.venv\Scripts\python.exe -m backend.demo
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.benchmark
cd web
npm run typecheck
npm run lint
npm run test:science
npm run build:selfhost
npm run build
npm audit
```

Scientific tests include analytical solutions, not only implementation snapshots. [Validation record](docs/VALIDATION.md) lists actual results and unverified deployment conditions.

The NOAA relief snapshot is included. To acquire it again, install the optional `requirements-data.txt` and run `python -m scripts.bootstrap_relief`. This uses Pillow for offline numeric GeoTIFF decoding; the application stack is unchanged.

## Self-hosting

```sh
docker compose up --build
```

The configuration serves `http://127.0.0.1:8080`, proxies `/api` through nginx and persists imports in a named Docker volume. Users need only a modern WebGL-capable browser. The API runs as a non-root user with one writable worker. The optional `compose.readonly.yaml` runs multiple workers against an immutable snapshot and disables mutations. Readiness checks, explicit frontend connection errors and a repeatable deployment probe are included. [Deployment modes, commands and acceptance limits](docs/DEPLOYMENT.md).

The actual two-worker service was verified locally through the portable frontend proxy. Docker Compose configuration passes, but the local Docker engine remains unavailable for image/nginx/container runtime validation.

For shared operation, configure institutional authentication and TLS at the reverse proxy. `OCEAN_API_TOKEN` can gate API calls after server-side authentication; do not embed service tokens in browser JavaScript. No organizational user-management system is claimed.

## Documentation and limits

- [Architecture and requirement coverage](docs/ARCHITECTURE.md)
- [Institutional web deployment](docs/DEPLOYMENT.md)
- [Automatic public INCOIS synchronization and source freshness](docs/SYNCHRONIZATION.md)
- [Timed forecaster evaluation and scoring protocol](docs/FORECASTER_EVALUATION.md)
- [Full problem-statement audit](docs/REQUIREMENTS_MATRIX.md)
- [CF instruments, plugins, ingestion and WMS/WCS setup](docs/EXTENSIONS_AND_SERVICES.md)
- [Versioned sensors, model readers and derived-product plugins](docs/EXTENSIBILITY.md)
- [Data contract, methods and endpoints](docs/DATA_CONTRACT.md)
- [Research rationale](docs/RESEARCH.md), also rendered as the workbench's Research & methods dossier
- [Executed validation and remaining checks](docs/VALIDATION.md)

Regional rectilinear Gregorian grids and documented CF profile/mission layouts are supported. Curvilinear/sigma/staggered models, arbitrary sample-varying instrument missions, distributed archive processing and operational identity controls require further engineering. WMS 1.3.0 and WCS 1.0.0 GET services are implemented and their XML responses schema-validated; full OGC certification, OPeNDAP serving and OGC EDR conformity are not claimed. The bundled Worker preview contains the classroom and datasets; the API-connected preview exposes imports and standards services.

This is a substantive research prototype with working real-data evidence, not a certified operational product or a guarantee of an SIH outcome.

## Larger data archives

[Scaling setup and measured limits](docs/SCALING.md) covers lazy mounted NetCDF time archives, geographic display subsets, binary frames, resource budgets and the executed 1.5 GiB synthetic benchmark. The optional `compose.archives.yaml` mounts a verified archive directory read-only. The browser upload limit remains 50 MiB.
