# INCOIS coverage and retrieval — 8 September 2026

The implementation indexes **all 16 scientific products advertised by the public INCOIS ERDDAP catalogue** at retrieval: four depth-resolved analyses, eleven surface/diagnostic products, and one individual Argo observation table. There are **86 gridded variables and 26,084 exact source time coordinates** (summed across products, not unique timestamps). All fifteen gridded products returned usable data. The observation table also returned data.

This is the complete inventory of this public ERDDAP, not a claim to possess every INCOIS internal archive, restricted forecast feed, LAS product or instrument stream. New public products require a catalogue refresh. There is no automatic synchronization scheduler.

## What is loaded and what is available on demand

- **Ocean lab:** full native monthly Kessler–McCreary temperature/count data for May–July 2026. Coverage is 30.5–119.5°E, 29.5°S–29.5°N; 90 × 60 columns and 24 depths, 5–2,000 m. Seven region presets subset every frame/depth/count using the same native indices. No regional resampling enters the diagnostics.
- **3D Explorer:** three most recent native frames from each of the four Argo analyses; monthly and ten-day Kessler–McCreary, monthly and ten-day variational analysis. Temperature and salinity are supported; McCreary spread is also supported. Historical selections open a full-domain native column dataset on demand. Those selections are process-local and may be reopened after restart.
- **INCOIS sources:** every source variable from every gridded product, all catalogue time coordinates, the actual depth coordinates where present, and explicit geographic selection. Newest-time, first-level snapshots contain all variables and are bundled for offline browsing. The API requests other times/depths/regions. Date selection resolves to a published timestamp, which is displayed before retrieval.
- **Surface display:** a source stride bounds each horizontal axis to 240 samples by default (API maximum 480). The map retains the actual sampled coordinates, exact source values and missing mask. It does not fabricate subsurface data from SST, atmospheric wind or diagnostic depth fields. The native NetCDF link removes display striding for the same requested time/level/region.
- **Argo observations:** all 23 exposed table fields are requested for bounded windows; the UI requests any archive day. The newest archived day, 23 April 2025, is bundled (one profile, 91 levels). Geographic markers and depth charts preserve coordinates, times and separate raw/adjusted channels. Source metadata and original QC are downloadable. Time, pressure and the selected variable must each pass QC 1 or 2 to appear in the strict chart. The table does not expose POSITION_QC or DATA_MODE; neither is invented. Empty source selections and acquisition failures are reported explicitly.
- **Terrain:** NOAA ETOPO 2022 numeric GeoTIFF, 30–120°E, 30°S–30°N, sampled at 0.25° (86,400 elevations) from the 15 arc-second source. Its EPSG:4326 pixel-is-area transform is checked. This is geographic context, not the model mask or navigational bathymetry. The upper-ocean depth lens is labelled; land and depths below 500 m use 35×.

## Scientific interpretation

The INCOIS analyses do not identify potential versus in-situ temperature. The adapter preserves analyzed temperature as a separate variable. It does not silently enable density diagnostics or compare that temperature against potential-temperature observations. VAM relative-error fields have ambiguous units relative to their labels; the source library retains them as published and never calls them standard deviation. McCreary salinity observation-count variables have erroneous salinity-unit metadata; their count units are explicitly corrected and documented. Source salinity is explicitly identified as practical salinity.

The existing HYCOM/Argo reference case, analytic test fixture, CF ingestion, model–observation diagnostics and OGC services remain available. The monthly snapshot, ten-day analysis, satellite archives and individual profiles have different dates and meanings; the UI shows the actual loaded timestamp rather than calling them all live.

The Explorer also includes a separate, real **HYCOM ESPC-D V02 current forecast snapshot**, covering the Indian Ocean at all 40 source depths down to 5,000 m. Full-column vectors, selected-depth vectors, streamlines, a current depth profile and three-frame playback are implemented. Its initialization and valid times are kept distinct from INCOIS analyses. See [current data and rendering](CURRENTS.md).

## Acquisition and operation

`scripts/inventory_incois.py` acquires metadata for every advertised scientific product. `backend.incois_catalog.build_catalog()` fetches exact source axes; irregular timestamps are not reconstructed from average spacing. `scripts/bootstrap_incois_catalog.py` prepares verified source snapshots, full-domain models and browser packets. `scripts/bootstrap_indian_relief.py` prepares NOAA numeric terrain.

For an administrator refresh, stop the API and run `python scripts/bootstrap_incois_catalog.py --refresh`, then restart the API and rebuild the frontend. This reacquires the public index, metadata and exact axes before replacing generated request caches and rebuilding snapshots. A failed download does not replace its existing source file. This is an explicit operation, not a background monitor. Metadata/axes and bundles are a reproducible snapshot of the retrieval date. Original snapshot files are preserved outside the evictable request cache.

API routes:

- `GET /api/incois/catalog` — catalogue and exact time axes.
- `GET /api/incois/grid?product=…&variable=…&index=…&depth=…&bbox=west,south,east,north` — bounded source selection.
- `POST /api/incois/open` with `{ "product": "incois_argo_mnt_McCreary", "index": 0 }` — register a full water column for an exact archived time; then use normal volume/binary/OGC/export endpoints.
- `GET /api/incois/observations?start=…&end=…&bbox=…` — at most seven days and 16 MiB; the UI defaults to one day.

Only catalogue products and variables are accepted; callers cannot provide arbitrary source URLs. Geographic bounds, depth/time indices, response byte limits and timeouts are checked. HTTPS verification remains enabled. NetCDF downloads are capped at 32 MiB, cache storage at 512 MiB, table cache at eight files, loaded models at 32, and existing API in-flight capacity controls still apply. Scientific file reads share the process lock used by the existing API; network transfer occurs outside that lock. The Docker recipe includes curl and trusted CA certificates. Docker was not executed on this host.

## Verification

The full backend suite passed 70 tests; the targeted catalogue and scale suite passed 17 tests after source preservation and shared-lock changes. All 86 bundled gridded fields were checked against their original NetCDF values and missing masks with zero numerical tolerance. All four volume domains/depths and temperature semantics were checked. Frontend scientific tests include exact multi-frame geographic subsetting and hemisphere labels.

Browser checks exercised basin/Arabian Sea switching, the global AMSR-E map, historical 2001 monthly selection opening a full 3D field, regional 3D sections, source date/depth entry and original-source exports. Additional final production/mobile checks are recorded in the release validation note. This is measured implementation evidence, not an assertion of operational certification or flawless behavior on every device.

Authoritative source catalogue: https://erddap.incois.gov.in/erddap/info/index.html

Machine-readable inventory with product-specific source links and metadata hashes: `data/incois-catalog/catalog.json`. Original metadata: `data/incois-catalog/*-axes.nc` and product JSON files. Full water-column manifests: `data/incois-catalog/volumes.json`. Numeric terrain source hash: `889133b5b9d4c8aaafcebe395d32c3356cb7b31395e78e30830ca7f381a2f924`.
