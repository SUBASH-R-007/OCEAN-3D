# Sensor, variable and derived-product extensions

Ocean3D has versioned extension packs for observation parsers, sensor metadata, scalar variable definitions, model readers and externally computed products. These use the same preview/import, catalog, rendering, comparison and export pipeline. The stack and dependency lockfiles are unchanged.

This completes the plugin-style design requirement for the documented geometries. It does not claim automatic support for every vendor file, a live instrument connection, an arbitrary renderer plugin or an operational ML forecast. The example files are explicitly synthetic; the ML example exercises an output contract without training or running a model.

## What is available

| Extension | Implemented behavior | Input boundary |
| --- | --- | --- |
| Existing CTD, Argo, BGC and glider adapters | CF profiles, native GDAC/IMOS/CCHDO, timestamps, QC, depth charts, source evidence | See [ingestion contracts](INGESTION.md) and [real instrument cases](INSTRUMENT_OVERLAYS.md) |
| Mooring | Fixed-position, fixed-depth time series; timestamp chart, sample-wise model matching and QC | Canonical table, one station/depth per ID |
| ADCP | Paired east/north velocity samples, converted units, one depth profile per timestamp, separately selectable cast IDs | Already earth-referenced velocities at physical bin depths; raw beam rotation, tilt and vessel-motion corrections are upstream tasks |
| HF radar | Paired total east/north surface samples, geographically located cell/station markers, time-series inspection | Canonical total-vector table; no radial-to-total inversion, invented depth profile or dense radar-grid renderer |
| Variables | Registered IDs, units, aliases, default ranges and optional reviewed CF names drive controls, normalization and exports | Scalar fields on supported grids, or scalar readings within supported sensor geometries; no inferred scientific unit conversion |
| Model readers | A trusted parser returns an open xarray Dataset and provenance; core performs chunk guards and normalization | Result must still satisfy the regional rectilinear time/depth/latitude/longitude contract |
| Derived and ML products | Registered outputs, product/model version, generation timestamp, input hashes, validation/limitations and ML artifact/training/domain metadata | Ingests precomputed CF fields; no pickle/ONNX/model execution, training service or automatic inference job |

The distinction between fixed-depth time series, vertical profiles and trajectories follows [CF discrete sampling geometries](https://cfconventions.org/Data/cf-conventions/cf-conventions-1.13/cf-conventions.html#discrete-sampling-geometries). The HF-radar contract accepts total east/north surface velocities; [IOOS describes total-vector products separately from radial measurements](https://ioos.noaa.gov/project/hf-radar/). Neither source implies that arbitrary native instrument files follow Ocean3D's small canonical table contract.

## Built-in discovery and examples

`GET /api/extensions` reports API version 1, installed packs/versions, sensors, product definitions, plugin variables and import formats. `GET /api/adapters` retains its existing format-discovery contract. The Data catalog includes **Installed extensions**; the import form lists formats from the registry and exposes downloadable fixtures under **Synthetic extension examples**.

Default packs are `backend.extensions.sensors`, `backend.extensions.products` and the clearly labelled `backend.extensions.example_product`. The last pack registers a synthetic ML-output example variable/product, not a trained model or imported dataset. To replace the example pack with institutional extensions:

```powershell
$env:OCEAN_EXTENSION_MODULES = 'my_institution.ocean_extensions'
python -m backend.server
```

Set `OCEAN_EXTENSION_MODULES` to an empty string in the service environment to disable the example pack. The first two core packs remain installed. Keep the required packs configured when restoring imports that depend on them. In containers, install the trusted package in the API image and set this environment variable through the institution's deployment configuration. No uploaded file can set it.

Generate the same small fixtures:

```powershell
python -m scripts.extension_examples --output tmp/extension-examples
```

The default checked-in browser examples are under `web/public/examples/extensions`. They contain three mooring readings at 50 m, three ADCP profiles with three depths, three HF-radar surface timestamps and a 3 × 4 × 4 × 4 analytic scalar field. They are not measured sensor data or ML predictions. Public download availability does not import them automatically.

## Sensor table contracts

Use the existing long/wide delimited schema. The first line must be exactly the appropriate marker:

| Adapter | First line | `instrument` value |
| --- | --- | --- |
| `mooring-csv` | `# ocean3d:mooring-v1` | `Mooring` |
| `adcp-csv` | `# ocean3d:adcp-earth-v1` | `ADCP` |
| `hf-radar-csv` | `# ocean3d:hf-total-earth-v1` | `HF radar` |

```csv
# ocean3d:mooring-v1
profile_id,instrument,longitude,latitude,time,depth,variable,value,unit,qc,synthetic
TRAINING-MOORING,Mooring,85,14,2025-09-03T00:00:00Z,50,temperature,28,degree_Celsius,1,true
TRAINING-MOORING,Mooring,85,14,2025-09-03T06:00:00Z,50,temperature,27.5,degree_Celsius,1,true
```

One `profile_id` identifies a station/cell at a fixed longitude/latitude. Moorings also require fixed depth. ADCP and HF-radar records require exactly one `u` and one `v` row at each timestamp/depth; a missing measurement is a null value with retained QC, not an omitted vector component. HF radar requires nominal surface depth 0 m. Current units can be m/s or explicitly converted cm/s; directions are east/north, not magnetic heading, radial speed or raw beam channels.

The parser rejects duplicate variable/time/depth samples and inconsistent locations. It splits ADCP station records into separate timestamped profiles, retaining `station_id`. Stationary series/cells carry actual `sample_times`; freshness checks use these times, and coverage uses each QC-eligible reading's time. It does not fill gaps between widely separated deployments. No stationary record is assigned a vehicle trajectory. Each output series/profile is limited to 4,096 timestamps and 20,000 variable samples, in addition to existing file/output limits.

The inspector uses a horizontal time axis for moorings and HF-radar cells and a vertical depth axis for ADCP/CTD profiles. QC-rejected and missing readings break plotted lines. Time-series model comparisons retain per-sample positions and timestamps. These scalar inspectors do not render radar coverage polygons or perform radar inversions.

## Write an extension pack

An installed Python module declares metadata and a registration function:

```python
from backend.plugins import register_sensor, register_observation_adapter
from my_institution.reader import parse_station_file

PLUGIN = {
    'api_version': 1,
    'id': 'institution-stations',
    'version': '1.0.0',
    'label': 'Institution station observations',
}

def register():
    register_sensor({
        'id': 'institution-station',
        'label': 'Institution station',
        'geometry': 'time-series',
        'description': 'Fixed position and depth; explicit source timestamps.',
    })
    register_observation_adapter(
        'institution-station', parse_station_file,
        container='netcdf', label='Institution station NetCDF',
        detector=lambda meta: meta['attrs'].get('source_contract') == 'station-v1',
    )
```

The parser returns a list of common observation dictionaries (`id`, instrument, longitude, latitude, UTC-offset timestamp, synthetic flag, source, data mode and samples). Each sample supplies canonical `variable`, `value` or null, nonnegative physical `depth`, QC, adjusted flag, error or null, and its own time/position when different. Declare `sensor_id` and the registered `geometry`. For stationary series also supply sorted `sample_times`, `time_range` and `station_id`. Existing built-in adapters are executable examples. `prepare_import` validates values, coordinates, required metadata, registered quantities, geometry and output budgets before catalog mutation.

Supported sensor geometries are `profile`, `time-series` and `surface-current`. A genuinely different topology still needs an appropriate reviewed renderer and extension to the shared contract; arbitrary frontend code is not dynamically injected by an upload.

For a new model reader, call `register_model_adapter(kind, parser, label=..., detector=...)`. Its parser returns `(open_xarray_dataset, provenance_dict)` and owns closing resources on its own failures. After return, the core owns/normalizes/closes the Dataset, rejects oversized storage chunks and uses the same model category throughout preview, browser selection, persistence and exports. The reader must not disguise unconverted curvilinear or sigma coordinates as physical rectilinear axes.

The entire versioned pack load rolls back changes to variables, observations, model readers, sensor definitions and products on any registration failure. Duplicate IDs and ambiguous detectors reject. Imported manifests record the adapter pack/version; restart restoration rejects a version mismatch. Pin code and definitions for reproducibility; migrating stored imports is an explicit administrator operation. This is a trusted in-process extension system, not a sandbox for untrusted Python packages. The legacy `OCEAN_ADAPTER_MODULES` observation-only mechanism remains supported.

## Register a derived or ML output

Register its scalar definitions with `register_variable`, then its product with `register_product`. See `backend/extensions/example_product.py` for the exact fields. Products have an ID, label, `derived` or `machine-learning` kind, version, output variable IDs, method and limitations. The outputs must be registered quantities. A source-specific quantity can declare `standard: null`; input fields must then supply `long_name` and canonical units. Ocean3D omits CF vocabulary identifiers for that quantity instead of inventing one. A declared CF identifier still requires administrator review against the standard-name table.

A variable automatically recognizes its own canonical ID and unit in addition to the listed source aliases. This allows native exports to be read back using the same definition even when aliases only list vendor spellings.

The NetCDF uses the normal four-axis regional model contract and these global attributes:

- `ocean3d_product_id`: installed product ID.
- `ocean3d_product_version`: exact installed version.
- `ocean3d_lineage`: JSON containing `generated_at`, 1–64 unique `inputs` (`id`, lowercase SHA-256), `validation` and `limitations`.
- For ML products, lineage also requires `artifact_sha256`, `training_data` and `inference_domain`.
- `synthetic=true` for test/example values.

Auto-detection selects `derived-cf`. A declared product cannot bypass lineage validation by choosing the generic model adapter. Normalized outputs must exactly match the registered output IDs. Product definitions/lineage survive preview, catalog/frame/evidence JSON and native NetCDF export. Single-variable exports retain the parent product metadata; a multi-output product export is a subset, not a complete re-importable multi-output product.

The uploaded file's SHA-256 is computed and verified on restart. Input/model-artifact hashes and training/validation claims are **declared provenance**: Ocean3D validates their structure but does not possess or independently verify those external inputs/artifacts. The interface does not call these claims certification or a confidence score. No model artifact is deserialized or executed. Training, prediction quality, uncertainty calibration, operational approval and inference scheduling remain responsibilities of the product producer.

## Validation

See [8 September executed validation](VALIDATION_2026-09-08.md). Tests exercise sensor geometry, timestamp-wise comparison, units, QC, invalid contracts, registered model readers, atomic rollback, product provenance, missing metadata, version mismatch, native masks/values and CF export behavior. Browser checks use the explicitly synthetic files, alongside retained real instrument regressions; they do not validate real mooring/ADCP/HF-radar forecast performance.

Public INCOIS polling is now implemented separately from sensor extensions; see [synchronization](SYNCHRONIZATION.md). The adapter contracts remain the integration point for additional institutional streams. Polling the public catalogue does not activate new vendor sensors or ML inference.
