# Ocean3D scientific data contract

Updated 7 September 2026.

## Official INCOIS objective analysis

`backend/incois.py` validates the official `incois_argo_mnt_McCreary` subset: INCOIS institution, rectilinear dimensions, metre depth, explicit practical salinity, source temperature units and integer temperature counts. The fixed May–July 2026 native grid is time=3, depth=24, latitude=18, longitude=17. Original NetCDF and metadata remain under `data/incois`, with source/converted SHA-256 validation on load.

`analyzed_temperature` and `temperature_spread` are separate source-specific variables, with descriptive names and Celsius units but no invented CF standard_name. The source does not identify potential versus in-situ temperature; these quantities never enter potential-temperature diagnostics or matching. The source report supports the Celsius interpretation. Source depth is 5–2000 m, not pressure. Practical salinity is retained without a thermodynamic conversion.

Counts describe observations within each native box or influence region at each depth. They are not unique float totals. The displayed support fraction uses valid T_ANALYZED cells over the full source depth range; it does not change with the display window. T_STDEV is spread about the analyzed mean, not a confidence interval or independent forecast error. The original S_BOXOBS/S_ROIOBS have inconsistent salinity units; only the correctly described temperature counts feed the support panel.

Monthly frames are sampled at their exact timestamps. The default 48-hour sampling-gap policy rejects interpolation across months. Horizontal display upsampling is bounded and mask-aware, with the unchanged 1° native resolution disclosed. Native exports omit a standard_name for the two source-specific quantities; CoverageJSON uses a label without a false vocabulary identifier.

## Model fields

Regional CF-style NetCDF needs one-dimensional `time`, `depth`, `latitude`, `longitude` coordinates (documented lon/lat/deptht/lev aliases accepted). At least one timestamp and two coordinates per spatial axis are required. Axes must be finite and unique, and are ordered before use. Time must decode to Gregorian/standard NumPy datetime; a singleton time supports exact sampling only. Longitude is normalized to −180…180; domains spanning over 180 degrees or crossing the seam are rejected.

Depth declares metres or kilometres and an explicit or default positive-down convention; positive-up depth is converted. Unsupported pressure/sigma/curvilinear/staggered grids require an upstream adapter. Regional subsetting is required before large archive import.

| Canonical variable | Meaning | Accepted input units |
| --- | --- | --- |
| temperature / thetao | Potential temperature at 0 dbar; standard_name=sea_water_potential_temperature required | Celsius or Kelvin |
| salinity / so | Practical salinity | PSU, 1, 1e-3 or 0.001 |
| u / uo | Geographic eastward velocity | m/s or cm/s |
| v / vo | Geographic northward velocity | m/s or cm/s |
| chlorophyll / chl | Chlorophyll-a mass concentration | mg/m³ or kg/m³ |

All variables use the same rectilinear coordinate dimensions. Packed NetCDF scale/offset and fill values are decoded by xarray. Standard names conflicting with supported semantics are rejected. Source arrays remain separate from display grids.

## Delimited casts

Required header:

```csv
profile_id,instrument,longitude,latitude,time,depth,variable,value,qc
CAST-1,CTD,85,14,2025-09-03T12:00:00Z,10,temperature,28.2,1
```

Optional fields: `data_mode`, `adjusted`, `error`, `synthetic`. One location/time per profile ID; explicit timestamp offset required. Use separate casts for moving gliders. Depth is metres positive down; values already use canonical units, including potential temperature in °C. Empty/nonfinite measurements remain missing. Imports allow at most 200,000 rows. Instrument errors must be finite and nonnegative when supplied. Duplicate depth/variable rows cannot define a physical diagnostic column.

Strict comparisons accept QC 1; lenient comparisons admit 1 and 2. QC 0 and 3–9 never enter those metrics. `adjusted=true` does not override a bad QC flag. Sensor error is not a confidence interval or total model uncertainty.

## GDAC Argo

Requires N_PROF, PRES, TEMP, PSAL, LONGITUDE, LATITUDE and JULD in the supported core layout. Supplied position/time QC must be 1; missing position/time QC is not evidence of verified accuracy. Parameter-specific processing mode is used where supplied. A/D parameters always use adjusted data and matching QC, even if the adjusted array is absent or entirely missing. There is no raw fallback. Every contributing pressure/salinity/temperature input participates in temperature eligibility.

GSW converts pressure to depth and in-situ temperature to potential temperature at 0 dbar. Negative practical salinity is excluded. CHLA is supported on the same level layout with explicit mg/m³ units and its parameter mode. This is not universal support for every BGC multidimensional format. Original measurement errors and pressure errors are retained; they are not propagated total uncertainties.

Observed physics uses paired QC-1 T/S levels, rejects known pressure errors over 20 dbar and reports unknown pressure accuracy. Both observed and model diagnostics censor gaps above 150 m, including the 10-m reference bracket. Missing or unreached crossings are null with explanatory status, never zero.

## API

| Method | Endpoint | Result |
| --- | --- | --- |
| GET | /api/health | Readiness |
| GET | /api/catalog | Model/profile inventory and provenance |
| GET | /api/volume | model, variable, index, resolution 8–64, optional maximum_depth; uniform display grid |
| GET | /api/profiles/{id} | model, variable, qc, max_gap_hours; native-grid comparison at observed time |
| GET | /api/coverage | model, variable, index, qc; observation-distance heuristic |
| GET | /api/diagnostics | model, longitude, latitude, index, optional profile/reference/density_delta |
| GET | /api/export/column.covjson | model, variable, index, longitude, latitude; CoverageJSON vertical profile |
| GET | /api/export/subset.nc | model, variable, index, optional bbox=west,south,east,north and maximum_depth |
| POST | /api/transect | JSON model, variable, index, start/end [lon,lat] |
| POST | /api/import?kind=model/argo/csv/tsv/txt | Multipart field file; validates before registry insertion |

Display arrays are longitude-fastest, then latitude, then positive-down depth. `null` means missing. Coordinates retain precision; scalar display values round to five decimals. Original source brackets are gathered before interpolation, without source decimation. Upper-500-m rendering uses up to 96 vertical display samples; it does not increase source resolution. The VTK texture reverses storage so positive z points upward.

`ocean3d.evidence.v1` exports UTC time, settings, model provenance, completed comparison/coverage, active physics results, optional frozen-field flow paths and display metadata. Scientific API exports return a CoverageJSON media type or a native-grid NetCDF attachment. The hosted bundled mode does not expose upload or live Python export endpoints. Keep original source files and citations alongside the evidence when reproducing results.

## Real case

`data/reference/case.json` records source requests, retrieval metadata, transformations, hashes and verification metrics. Run `python -m scripts.bootstrap_reference` to reproduce acquisition from fixed public URLs, then `python -m backend.demo` to regenerate browser cases. The reference loader verifies the converted model checksum before registration. Argo source attribution and its DOI are retained in the dossier and manifest.
# Extension contract — 7 September 2026

The current service also accepts `kind=cf-profile` and exposes `/api/adapters`, `/api/ogc/wms` and `/api/ogc/wcs`. Administrator variable definitions drive canonical scalar handling. Imports can use `Idempotency-Key: SHA256:adapter`; manifests are replaced atomically and restored on restart. See [CF layouts, QC, temperature conversion, plugins and protocol details](EXTENSIONS_AND_SERVICES.md) for the supported contract and [requirement coverage](REQUIREMENTS_MATRIX.md) for its limits.

## Archive and display transport extension

Administrator-mounted time archives use exact normalized spatial-grid agreement, verified file hashes and non-overlapping timestamps. Display ROI queries preserve original bracketing masks; binary float32 frames are separate from native exports. Resource limits, packet layout and deployment constraints are specified in [SCALING.md](SCALING.md).
