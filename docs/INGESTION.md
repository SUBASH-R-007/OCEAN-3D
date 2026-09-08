# Multi-format ingestion

The scientific API uses xarray/netCDF4 and the existing bounded Dask pipeline. There is no stack change. Open **Data catalog → Bring your ocean data**, select a file, review its validation report, then choose **Add validated dataset**. Format detection uses file signatures and source metadata, not the filename. Detection is also available to automated API clients.

## Supported files

| Input | Supported contract |
| --- | --- |
| NetCDF 3/4 model | Regional rectilinear longitude, latitude, depth and Gregorian time; one or more registered scalar/current variables. Standard coordinate names/aliases or CF `standard_name`; auxiliary coordinates such as `longitude(x)` are supported without regridding. Existing missing-value/scale-factor decoding, unit conversion and bounded interpolation remain intact. |
| Argo GDAC | Core and BGC profiles, adjusted/raw channel policy and parameter QC; potential-temperature conversion through GSW. |
| CF discrete profiles | Profile, trajectoryProfile and timeSeriesProfile; orthogonal, incomplete, contiguous-ragged and indexed-ragged layouts. One position/time per cast, physical depth, explicit variable definitions and quality meanings. |
| IMOS native glider | Native PROFILE/PHASE, per-sample coordinates/time/depth, documented QC and units. |
| CCHDO native CTD | Native pressure, CTD temperature/salinity, cast metadata and WOCE QC; GSW pressure/depth conversion. |
| Delimited UTF-8/ASCII | Long or wide schema; comma, tab, semicolon, pipe or whitespace. UTF-8 BOM, blank lines and comment preambles before the header are accepted. CSV-style quoted fields and embedded newlines work with explicit delimiters; whitespace tables support quoted fields within one line. |

Model grids need at least one time and two coordinates per spatial axis. The regional domain cannot cross the longitude seam or span more than 180°. Curvilinear, sigma/hybrid, projected and non-Gregorian grids require a source adapter or upstream conversion. NetCDF groups, arbitrary vendor layouts and all CF feature types are not claimed. Metadata validation is not a general CF compliance certification. Files with insufficient metadata are rejected rather than guessed.

The implementation follows [xarray decoding and chunking](https://docs.xarray.dev/en/stable/generated/xarray.open_dataset.html) and the supported subset of [CF discrete sampling geometries](https://cfconventions.org/Data/cf-conventions/cf-conventions-1.13/cf-conventions.html#discrete-sampling-geometries). Source masks and scale/offset metadata are decoded before canonical values are exposed; the original uploaded bytes are retained.

## Text schema and unit rules

Every table requires `profile_id,instrument,longitude,latitude,time,depth`. Header aliases are `lon`, `lat`, `timestamp`/`date_time`, `depth_m` and `units`. Headers are case-insensitive and trimmed; duplicate or ambiguous names reject. Timestamps require an explicit UTC offset. Depth is positive down; optional `depth_unit` accepts m or km. Pressure is not relabelled as depth.

Long tables add `variable,value`, with optional `unit,qc,error,adjusted,standard_name`. Wide tables have one registered variable/alias column per measurement, with optional `<column>_unit`, `<column>_qc`, `<column>_error`, `<column>_adjusted`, `<column>_standard_name`. Common `qc`/`unit`/`error` fields can supply defaults, but per-variable fields are preferable. Unknown fields and variables reject with a record-level message instead of being silently discarded. Register a new scalar definition or adapt the source schema first.

```csv
profile_id,instrument,longitude,latitude,time,depth,temperature,temperature_unit,temperature_qc,u,u_unit,u_qc,synthetic
EXAMPLE,CTD,85,14,2025-09-03T12:00:00Z,10,300,K,1,20,cm/s,1,true
```

This explicitly synthetic row yields 26.85 °C potential temperature and 0.2 m/s eastward current. `temperature` always means potential temperature; an explicit incompatible standard name rejects. The generic text adapter does not infer that an unqualified vendor temperature is potential temperature.

- Celsius/Kelvin, m/s–cm/s and mg/m³–kg/m³ conversions are explicit. Temperature spread in Kelvin converts as a difference, without a 273.15 offset. Practical salinity accepts equivalent dimensionless/PSU spellings; mass-based salinity does not silently become practical salinity.
- Omitted built-in units use the documented canonical units for compatibility with the original table schema, and every assumption appears in the validation report. Plugin variables always require explicit canonical units. Original values, units, depths and record numbers remain attached to normalized readings.
- Blank, NA, N/A, NaN and null measurements stay missing. Infinity and malformed numbers reject. Missing QC remains unknown (0); QC 1/2/other are reported separately. Negative errors and non-integer quality flags reject. Unit conversion scales measurement errors without applying value offsets.
- Optional `synthetic` and `adjusted` must be true/false. Instrument, data mode and synthetic status must agree within one profile ID. Per-row positions and times may vary; they are retained for model matching. Paths connect supplied samples and are not inferred vehicle trajectories.
- Limits: 50 MiB per upload, 200,000 normalized values for text, 10,000 profiles. Native/CF adapters retain their documented 200,000-level limits. Adapter output has an additional one-million-variable-sample ceiling.

The interface provides long and wide synthetic examples. Original files, hashes and validation reports survive API restarts. The observation CSV export is an evidence report, with model/QC columns; it is not the import template.

## API and repeatable processing

`GET /api/adapters` advertises registered formats, labels, file types, variable definitions and limits. The frontend consumes this registry, including trusted custom adapters.

`POST /api/import/inspect?kind=auto` takes multipart `file`. It executes the same parser/validation contract as import, returns the detected adapter, hash, variable units, counts, depth/time ranges and QC/warnings, then closes/removes its temporary file. It never registers a model/profile or writes a persistent import manifest. Model inspection performs a bounded sample decode, not a full scan of every cell. The preview does not establish scientific accuracy.

`POST /api/import?kind=auto` validates and persists the original file with an atomic manifest and report. Explicit adapter IDs remain supported. `Idempotency-Key: SHA256:requested-adapter` deduplicates the resolved adapter and payload; automatic and explicit requests can find the same existing import. A failed parser or wrong idempotency key leaves neither a registered dataset nor a temporary import file. The UI verifies that the file still matches the preview checksum before submitting it. The API reparses the upload rather than trusting a client preview.

All endpoints use the existing token and bounded-work policy. The frontend requires the scientific API for uploads; the standalone snapshot does not pretend to persist scientific data in browser storage.

For producer-driven ingestion, use `scripts.ingest_inbox`. A producer writes `mission.nc.ready.json` only after closing the data file, with `{"kind":"auto","sha256":"..."}`. The command verifies the hash, uploads idempotently and writes an atomic receipt without moving/deleting source files. Receipts distinguish requested adapters; failures return a nonzero process status. Schedule the one-shot command using institutional infrastructure if repeated ingestion is needed. This work does not activate a live feed or scheduler.

## Add a variable or source

Set `OCEAN_VARIABLE_MANIFEST` to an administrator-owned definition list; `config/variables.example.json` supplies oxygen in mmol m-3. No renderer change is needed. IDs, units, CF standard name, aliases and default display range feed model/text/CF parsing, catalog controls, scalar rendering and exports. Unsupported unit conversions require an explicit adapter, not just an alias.

A trusted installed Python module may expose:

```python
from backend.plugins import register_observation_adapter
from my_institution.reader import parse_profiles

def register():
    register_observation_adapter(
        'institution-sensor', parse_profiles,
        container='netcdf', label='Institution sensor',
        detector=lambda meta: meta['attrs'].get('source_contract') == 'institution-v1',
    )
```

Set `OCEAN_ADAPTER_MODULES=my_institution.ocean_adapter` before API startup. It is administrator-owned configuration, never an uploaded module or path. The parser receives a file path and returns validated common profile dictionaries. The metadata detector receives container plus NetCDF attributes/dimensions/variable metadata (or a bounded text header). Multiple matching detectors reject and request an explicit format. Container metadata determines signature validation and the persisted .nc/.txt suffix; custom NetCDF adapters therefore follow the same path as built-ins. Registry loading rolls back additions if registration fails.

Existing trusted `register_observation_adapter(kind, parser)` calls remain supported, defaulting to text. The versioned `OCEAN_EXTENSION_MODULES` mechanism additionally registers sensor geometries, model readers, scalar definitions and derived products atomically. A `register_model_adapter` parser returns an open xarray Dataset and provenance; the core owns chunk guards, normalization and closing. Imported manifests record the pack version, and restoration rejects a mismatch. No unreviewed plugin code runs from a data upload.

The built-in mooring, ADCP and HF-radar canonical tables use explicit first-line contract markers and preserve their distinct geometries. Precomputed derived/ML NetCDF fields require a registered product definition and validated lineage. See [sensor and product contracts, sample files and plugin instructions](EXTENSIBILITY.md). A source-specific scalar can declare a null standard name with an explicit long name and canonical units; the system does not invent a CF vocabulary identifier.

## Verification

See the dated validation log for final test/build/browser results. Targeted tests cover all five delimiters, long/wide tables, native unit/error preservation, moving samples, schema/unit/QC rejection, packed NetCDF with auxiliary axes, real-source detection, plugin variables, preview isolation, idempotent persistence, restart restoration and custom NetCDF adapters.
