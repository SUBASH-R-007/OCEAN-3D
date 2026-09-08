# Instruments, plugins, standards and classroom

The current automatic-detection, validation-preview, text-schema and source-plugin workflow is documented in [INGESTION.md](INGESTION.md). The import selector now reads the server registry. Existing canonical-unit tables remain compatible; explicit convertible text units and long/wide layouts are also supported.

For the versioned pack API, working mooring/ADCP/HF-radar contracts, model-reader registration and derived/ML product provenance, use [EXTENSIBILITY.md](EXTENSIBILITY.md). The new time-series inspector preserves individual timestamps and QC gaps; it does not convert surface or stationary records into invented depth profiles.

## Native CF profiles

Choose **Data catalog → Glider / CTD / BGC · CF profiles** and upload a bounded NetCDF file. `featureType` must be profile, trajectoryProfile or timeSeriesProfile. The file needs a one-dimensional `cf_role=profile_id`, one position and Gregorian timestamp per profile, depth in m/km with positive direction, and explicitly named/unit-qualified variables. Contiguous ragged row counts, indexed ragged profile indices, orthogonal or incomplete arrays are supported. Moving missions use a parent trajectory/platform ID and a zero-based profile-to-platform index.

Quality is mapped from explicit `ancillary_variables`, `flag_values` and `flag_meanings`. Known good/probably-good/bad/missing meanings map to 1/2/4/9; unrecognized/missing quality stays 0. In-situ `sea_water_temperature` requires colocated practical salinity: GSW converts depth/latitude to pressure, SP to SA and temperature to potential temperature at 0 dbar. Both source quality flags contribute, and source temperature remains in each row. Potential temperature is accepted directly with canonical units. No uncertainty propagation is claimed.

The downloadable `web/public/examples/synthetic-glider.nc` is explicitly synthetic: four moving casts, seven depths per cast and three variables. Regenerate with `python -m scripts.build_cf_example`. It exercises the parser and interface; it is not a retrieved INCOIS glider mission. Cast joins are straight geographic-context lines, separated after 48-hour gaps, not reconstructed underwater tracks.

Source: [CF 1.12 discrete sampling geometries](https://cfconventions.org/Data/cf-conventions/cf-conventions-1.12/cf-conventions.html#discrete-sampling-geometries). The implementation supports the layouts listed above rather than every CF representation.

## Add a scalar without changing the renderer

Set `OCEAN_VARIABLE_MANIFEST` to an administrator-owned JSON array, such as `config/variables.example.json`, before starting the API. Each definition has id, label, displayed unit, canonical NetCDF unit, standard name (or null for a source-specific quantity), aliases, accepted equivalent unit spellings and a display range. The supplied oxygen example requires mmol m-3; it does not silently convert mol m-3. Conflicting IDs/aliases and malformed definitions reject atomically. Uploaded files cannot change this registry.

The registry feeds model normalization, the catalog, variable controls, scalar rendering, canonical-unit CSV/CF observations, WMS and NetCDF/CoverageJSON exports. Thermodynamic diagnostics still require their specific temperature/salinity inputs. A new machine-learning scalar can enter the same contract after its scientific definition and provenance are reviewed; this does not train or validate a model.

For a specialized instrument adapter, call `backend.plugins.register_observation_adapter(kind, parser)` from trusted deployment code before serving. A parser returns common observation dictionaries. The API validates them and applies ID scoping, hashes and persistent manifests. Registered sensor geometries select profile or stationary/surface time-series inspection. HF-radar total-vector cells are supported by the canonical adapter; raw radials and dense radar coverage surfaces still require suitable upstream processing and visualization.

## Automated, repeatable ingestion

After a producer closes `mission.nc`, it writes `mission.nc.ready.json` containing `kind` and the file's SHA-256. Run:

```text
python -m scripts.ingest_inbox /path/to/inbox --endpoint http://127.0.0.1:8000
```

The command verifies the hash, sends the file to the ordinary import endpoint and records a receipt. The API accepts `Idempotency-Key: SHA256:adapter` and reuses a restored matching import. A crash between upload and receipt therefore does not require a duplicate dataset. The command leaves source files intact. Use the institution's job scheduler for repeated runs; no scheduler or outside sensor connection is installed by this command. `OCEAN_API_TOKEN` is read from the environment when configured. Network failures, corrupt files and incomplete producer writes remain errors rather than fake successful updates.

## WMS and WCS

The same-origin `/api/ogc/wms` and `/api/ogc/wcs` endpoints use the scientific API's token policy. The Data catalog includes working selected-map and coverage links when connected. Configure a trusted reverse proxy/Host policy for the institutional public endpoint; capabilities advertise the request endpoint.

WMS 1.3.0 supports GET GetCapabilities, PNG GetMap and JSON GetFeatureInfo. Layer IDs are `model:variable`. Empty STYLES selects thermal; thermal, saline and balance are advertised. Optional `COLORSCALERANGE=min,max` is a documented vendor parameter. Pixel centres are sampled in geographic coordinates; masks remain transparent when requested. EPSG:4326 BBOX is south,west,north,east; CRS:84 BBOX is west,south,east,north. Elevation is negative depth in metres. Time and elevation must match advertised entries. Limits: one layer, at most 1024 pixels per side and 262,144 total pixels.

WCS 1.0.0 supports GET GetCapabilities, DescribeCoverage and GetCoverage. Coverage IDs are `model:variable:depthIndex`. TIME selects one exact timestamp; omission uses the latest available. BBOX is west,south,east,north and CRS is EPSG:4326 under WCS 1.0 conventions. FORMAT is NetCDF. Responses preserve native coordinates, masks and the selected depth. The service advertises interpolation=none, so requested resampling/reprojection is rejected. WCS 2.0, POST/XML binding, OPeNDAP and formal certification are not claimed.

Reference specifications and schemas: [OGC WMS](https://www.ogc.org/standards/wms/), [OGC WCS](https://www.ogc.org/standards/wcs/), [WMS 1.3 schema](https://schemas.opengis.net/wms/1.3.0/), [WCS 1.0 schema](https://schemas.opengis.net/wcs/1.0.0/). Actual capabilities, coverage description and WMS error responses pass the official XSDs. This is schema validation plus targeted protocol tests, not the full TEAM Engine conformance suite.

Reproduce XML checks with `python -m scripts.export_ogc_validation`, then `python scripts/validate_ogc_xml.py` using a validation-only Python environment containing lxml. `--fetch` populates the official OGC/W3C schema cache using verified HTTPS. The supplied cache manifest records all source URLs and hashes. No lxml runtime dependency was added to the API.

## Public classroom

The Learn tab offers four lessons: water-column depth, temperature isosurfaces, current interpretation and observation quality. Each changes real Explorer settings and includes an interpretation question with feedback. Users can freely change the scene controls. The demonstration is labeled synthetic; it never presents a current streamline as a forecast trajectory. The classroom works in the bundled frontend without the Python API.
