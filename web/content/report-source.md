# Ocean3D: from a model picture to defensible evidence

SIH26067 · Research and implementation dossier · 8 September 2026

Audience: the SIH team, scientific evaluators and INCOIS integration engineers. Scope: a regional Indian Ocean workbench for depth-resolved model fields and instrument profiles. The supplied problem statement defines the requirements; implementation suggestions inside the accompanying documents were treated as reference material.

## Coverage beyond the Bay of Bengal

The 8 September implementation indexes all 16 scientific products advertised by the public INCOIS ERDDAP: four water-column analyses, eleven surface/diagnostic products and the individual Indian Argo table. Its 86 gridded variables expose 26,084 exact source time coordinates across products. Every gridded product has a successful newest-time snapshot; historical dates and selected depths/regions load through the scientific API. [INCOIS: public dataset catalogue](https://erddap.incois.gov.in/erddap/info/index.html).

Both monthly and ten-day Kessler–McCreary and variational analyses now have full native Indian Ocean volumes: 30.5–119.5°E, 29.5°S–29.5°N and 24 levels down to 2,000 m. Ocean lab defaults to the full basin and includes seven geographic presets with NOAA ETOPO 2022 terrain sampled at 0.25°. The original Bay subset below remains a reproducible evidence case; its local metrics must not be read as basin-wide metrics.

The source library keeps surface-only products on geographic maps and opens compatible depth-resolved fields in the 3D Explorer. Individual Argo profiles preserve raw/adjusted channels, coordinates, timestamps and source quality flags. All 23 exposed table fields are requested. The newest archived day contains one profile with 91 raw levels; unavailable adjusted values remain unavailable. Historic and restricted INCOIS feeds outside this public ERDDAP are not silently claimed as integrated. The writable service now polls public INCOIS ERDDAP every six hours, with a manual check, immutable catalogue revisions, source dates, visible failures and restart restoration. All 16 public products were acquired successfully on 8 September 2026. The newest analyzed fields still end in July 2026 and the Argo table in April 2025; a successful refresh is not evidence of a current operational feed. The bundled frontend does not run this service.

## The decision

Keep React, VTK.js and FastAPI/xarray. The strongest contribution is a complete inspection workflow: reveal the water column, compare a quality-approved observation at its actual timestamp, explain the physical diagnostics, and export the evidence with its provenance. Replacing this working stack would not resolve the remaining scientific or deployment gaps.

This implementation combines official INCOIS Argo objective-analysis fields, GPU volumes, intersecting 3D sections, masked isosurfaces, geographic context, horizontal current streamlines, TEOS-10 diagnostics on compatible fields, a retrieved HYCOM–Argo case and scientific exports. It remains a regional research prototype. A hackathon result, operational acceptance and superiority over other systems cannot be guaranteed.

The project uses established numerical methods. Its proposed novelty lies in how source quality, unsupported comparisons, threshold sensitivity and reproducibility become part of one visible workflow. That is a design claim to evaluate with users, not a claim to have invented volume rendering or mixed-layer science.

## What the problem actually requires

The brief asks for browser-based 3D fields of temperature, salinity and currents; overlays for Argo, gliders, CTD and BGC instruments; volume, slice, isosurface and time controls; profile inspection; configurable color and opacity; modular NetCDF and text ingestion; and deployment suitable for INCOIS. It also asks for interoperability through established ocean-data services and standards.

The implemented core covers the visual and inspection workflow. Regional rectilinear CF NetCDF, GDAC Argo, CF profile collections and delimited tables enter a shared scientific contract. Native CF imports now support orthogonal/incomplete and ragged profiles, including moving missions with profile-to-platform indices. WMS 1.3 maps and feature queries and WCS 1.0 native-depth NetCDF coverages run on the scientific API. Staggered/curvilinear model grids, arbitrary sample-varying missions, distributed archives and OPeNDAP serving remain integration work.

## INCOIS data from the official service

The workbench includes the INCOIS Argo monthly Kessler–McCreary objective-analysis product, downloaded from INCOIS ERDDAP on 7 September 2026. The Bay of Bengal subset covers May–July 2026, 79.5–95.5°E and 5.5–22.5°N. It retains a native 1° grid and 24 depths from 5 to 2,000 m. These dimensions come from the current NetCDF; older descriptions of 19 levels do not override the retrieved metadata. [INCOIS: product metadata](https://erddap.incois.gov.in/erddap/info/incois_argo_mnt_McCreary/index.html).

The input contains analyzed temperature, practical salinity, temperature spread, analysis-relative RMSE and observation counts. Ocean3D visualizes temperature, salinity and spread while preserving all eight downloaded variables. The INCOIS method uses surrounding Argo profiles to estimate grid values; the field is not a direct measurement at every displayed point. [INCOIS: objective-analysis technical report, version 2](https://argo.ucsd.edu/wp-content/uploads/sites/361/2020/05/Incois_Argo_ObjectiveAnalysis_Ver2.0.pdf).

T_ANALYZED uses “degs” without a thermodynamic standard_name. Celsius is interpreted from the report, but potential versus in-situ convention is left unspecified. The separate analyzed_temperature quantity cannot enter potential-temperature comparisons or density calculations. Salinity-count variables have inherited PSU/salinity metadata despite being counts; the support panel instead uses the temperature-count variables and reports integers. Spread is variability about the analyzed mean, not an independent error estimate or confidence interval. These are findings from the source metadata, not corrections endorsed by INCOIS.

For July, 1,043 of 4,564 valid temperature grid cells have observations in their own 1° box: approximately 23%, calculated over the full native depth subset. Counts are repeated per cell and depth and cannot be summed to obtain unique floats. The surrounding influence region supplies 1–29 profiles per valid cell. The source file is 712,584 bytes with SHA-256 0eca3a4f7a98c0d7807da7e098fb4543ccc5d861a917fbb510d23f5cb02f870c. Its request URL, full reuse notice and transformations remain in the provenance manifest.

Bounded interpolation into a 36 × 36 horizontal display grid and 72 levels in the upper-500-m view reduces raster steps without increasing native resolution. Missing contributing corners invalidate a sample; intersecting sections omit unsupported faces. Frames represent monthly analyses. The source library can load synchronized full-basin generations separately from this fixed research case. There is no interpolation between monthly timestamps or INCOIS current velocity in this selected product. GODAS/IGORA catalogues were reachable, but LAS data requests timed out; those products are not claimed as integrated.

## Ocean lab: structure, change and source support

Ocean lab adds actual NOAA ETOPO 2022 basin relief to the INCOIS thermal field. Three first-crossing surfaces at 28°C, 24°C and 20°C use staggered cutaways so the water-column structure is visible. A 3D probe selects the nearest native INCOIS column and links it to monthly profiles, depth brackets and observation counts. The NOAA extract is a numeric 230 × 220 GeoTIFF sampled at 0.1°, rather than a painted seabed. [NOAA NCEI: ETOPO 2022](https://www.ncei.noaa.gov/products/etopo-global-relief-model).

The change lens compares two monthly analyses at a chosen isotherm. It computes the first downward crossing on native depth levels, linearly interpolating only its two adjacent depths. A missing level before the crossing or a depth gap over 150 m makes it unavailable. If the shallowest value is already colder, the crossing is not extrapolated upward. Positive change means a deeper analyzed isotherm; this is not water-parcel motion, a causal explanation or a thermocline-depth definition.

The July-minus-May 20°C case has 172 paired native columns. Only 7 have local observations at both crossing brackets. The local-observation filter makes this distinction visible in 3D: isolated pairs remain as points and depth connectors, and a continuous face requires four adjacent eligible columns. Surrounding profiles can still support the other analyzed columns; local presence is not an accuracy threshold. Selecting the largest absolute change leads to 83.5°E, 10.5°N: the crossing shifts from approximately 139.6 m to 93.7 m, a 45.9 m shallowing. Both native brackets and their counts remain inspectable. These are calculations from this snapshot, not general ocean claims.

In thermal views, the depth lens expands the top 500 m by 400–1,600×, default 1,000×, with deeper relief and land at 35×. The transform is continuous but its scale changes at 500 m. Relief-only mode uses uniform 35×. Geometry, captions and exports preserve this distinction. Terrain does not repair INCOIS missing cells; surface tessellation does not increase native resolution. Investigation exports include source hashes, periods, threshold, location, native profiles and crossing support. The contribution is a traceable interaction workflow built with established methods.

## Where differentiation is defensible

INCOIS launched Digital Ocean in December 2020, and Argo maintains a comparison of established visualization tools. These are clear prior art. Ocean3D should be presented as a focused answer to this problem statement, with evidence of usability and scientific correctness, rather than as the first ocean data platform. [Government of India: Digital Ocean launch, 2020](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1684418&lang=2&reg=48). [Argo: visualization tool comparison](https://argo.ucsd.edu/data/data-visualizations/data-visualization-comparisons/).

Five contributions are concrete enough to demonstrate:

- Evidence with explicit abstention: paired profiles show accepted levels, QC exclusions and unsupported samples alongside bias and RMSE. An invalid comparison yields no invented score.
- Physics with method sensitivity: mixed-layer and barrier-layer diagnostics show their definitions, crossing brackets and sensitivity to a chosen density threshold.
- Two complementary data cases: an analytical fixture tests expected behavior; a retrieved model and real cast demonstrate provenance, conversion and matching. A rejected real cast tests the failure path.
- Reproducible investigation: view settings, source hashes, metrics, methods and exclusions travel with an evidence export. Local deployments also export CoverageJSON and native-grid NetCDF.
- Native-bracket monthly change: 3D isotherm displacement is linked to its source profiles and an explicit local-observation filter; isolated eligible columns never become fabricated continuous surfaces.

Coverage-gap ranking is an additional inspection aid. It measures distance to an eligible observation within a time window. It is not a calibrated uncertainty estimate, an autonomous sampling plan or a safe vessel route.

## A real Indian Ocean case, with its limits

The bundled historical case covers approximately 86–87°E and 2.5–3.5°N in the eastern equatorial Indian Ocean, south of the Bay of Bengal. It pairs a HYCOM analysis subset at 15:00 and 18:00 UTC on 1 September 2023 with Argo float 5904729, cycle 274, observed at 2.9967°N, 86.5021°E at 15:49:17.001680 UTC. Data were retrieved on 7 September 2026. [HYCOM: 2023 temperature and salinity service](https://tds.hycom.org/thredds/dodsC/GLBy0.08/expt_93.0/ts3z/2023.html). [Argo: source profile D5904729_274.nc](https://argo-gdac-sandbox.s3.eu-west-3.amazonaws.com/pub/dac/aoml/5904729/profiles/D5904729_274.nc).

The retrieved HYCOM source has two timestamps, 20 native depths and a 13 × 7 horizontal grid after the explicitly requested strides. The source model extends to 4,000 m. The cast contributes 1,001 eligible matched levels between approximately 4 and 1,983 m. Model potential temperature has bias +0.10545°C and RMSE 0.65527°C against this cast; practical salinity has bias +0.02574 and RMSE 0.12511. These are results of the included files and matching implementation, not values quoted from a publication.

This is one cast and a small, already subsampled regional model extract. It cannot establish general forecast skill. The cast's assimilation status in this HYCOM analysis was not established, so the comparison must not be described as independent validation. Unweighted level-wise RMSE also reflects this cast's vertical sampling distribution.

The second real profile, float 2902394 cycle 290, contains 511 missing adjusted salinity values flagged bad. They are excluded, and its potential-temperature comparison has zero eligible levels because the salinity needed for conversion is unavailable. The rejection is intentionally retained in the demonstration. [Argo: rejected source profile](https://argo-gdac-sandbox.s3.eu-west-3.amazonaws.com/pub/dac/aoml/2902394/profiles/D2902394_290.nc).

The reproducibility manifest records original request URLs, retrieval time, transformations, source and converted-file SHA-256 values, and verification metrics. Argo's public object-store distribution identifies Euro-Argo as provider, CC BY 4.0 terms and dataset DOI 10.17882/42182. The acquisition script needs no embedded credentials. [Registry of Open Data: Argo GDAC](https://registry.opendata.aws/argo-gdac-marinedata/).

## Scientific meaning survives ingestion

Potential temperature and in-situ temperature cannot be subtracted as though they were identical. Both retrieved HYCOM water temperature and Argo TEMP are converted to potential temperature at 0 dbar using TEOS-10, with practical salinity, pressure and location. Pressure and depth use their physical sign conventions. Negative practical salinity is rejected before conversion. Model imports must identify the supported potential-temperature definition. [GSW: potential temperature from in-situ temperature](https://www.teos-10.org/pubs/gsw/html/gsw_pt0_from_t.html). [GSW: Absolute Salinity from Practical Salinity](https://www.teos-10.org/pubs/gsw/html/gsw_SA_from_SP.html).

For adjusted and delayed-mode Argo parameters, the adapter selects adjusted values and their associated QC. It does not silently substitute raw data when adjusted values are missing. Parameter-specific mode metadata takes precedence where supplied. Strict comparisons accept QC 1; the separate lenient option also admits QC 2. Temperature conversion requires eligible pressure, salinity and temperature together. [Argo: how to use profile files](https://argo.ucsd.edu/data/how-to-use-argo-files/). [Argo: data-quality FAQ](https://argo.ucsd.edu/data/data-faq/).

The comparison engine performs bounded linear interpolation in longitude, latitude, depth and time at the observation timestamp. Only corners with positive interpolation weights contribute. A missing contributing corner invalidates the sample, but a zero-weight missing neighbor cannot erase an exact valid grid node. There is no extrapolation, and time brackets over 48 hours are rejected by default. A single model timestamp supports exact-time comparisons only.

Depth is positive down in metres. Axes must be finite, ordered and unique; unsupported calendars and coordinate systems fail validation. CSV/TSV temperature must already be potential temperature in °C. One position and timestamp belong to each profile ID; moving platforms must be separated into casts. [CF conventions: coordinate semantics](https://cfconventions.org/cf-conventions/cf-conventions.html).

## Mixed layers, barriers and stratification

The density mixed-layer depth is the first crossing of a 0.03 kg/m³ potential-density-anomaly increase relative to 10 m. A separate temperature-departure depth uses an absolute 0.2°C departure. Crossings are linearly interpolated within their reported native-level bracket. The 10-m reference and these thresholds follow the cited climatological method. [de Boyer Montégut et al., 2004: mixed-layer depth](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2004JC002378).

Barrier-layer separation uses a different density criterion: the density change equivalent to cooling the reference potential temperature by 0.2°C while holding reference salinity fixed. The implementation adapts this criterion to TEOS-10. It subtracts that density-crossing depth from the cooling-only temperature-crossing depth. Positive separation indicates a barrier layer; negative separation indicates compensation. Using absolute temperature departure or the fixed 0.03 threshold here would conflate distinct definitions. [de Boyer Montégut et al., 2007: barrier and compensated layers](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2006JC003953).

GSW derives Absolute Salinity, Conservative Temperature, sigma-zero and buoyancy frequency squared, N². Calculations respect the supported thermodynamic domain. Negative N² is retained because clipping it to zero would conceal instability in the sampled profile. [GSW: Conservative Temperature](https://www.teos-10.org/pubs/gsw/html/gsw_CT_from_pt.html). [GSW: sigma-zero](https://www.teos-10.org/pubs/gsw/html/gsw_sigma0.html). [GSW: N²](https://www.teos-10.org/pubs/gsw/html/gsw_Nsquared.html).

Project policies add conservative limits: no interpolation across native vertical brackets exceeding 150 m, including the reference bracket; observed diagnostics use paired QC-1 temperature and salinity; known pressure errors over 20 dbar are excluded. Unknown pressure accuracy remains an explicit limitation. An unresolved crossing is reported as unresolved, not as zero metres. The 0.02/0.03/0.05 density sensitivity display expresses method choice, not confidence intervals.

## Advanced rendering with honest geometry

VTK.js supplies browser scientific rendering and volume-mapper controls. Ocean3D keeps an owned rendering context and camera while time frames and display properties change, separates data updates from transfer-function changes, and disposes scene resources on teardown. It exposes cutaways, explicit opacity, finer ray sampling, slices and masked isosurfaces. [VTK.js: React integration](https://kitware.github.io/vtk-js/docs/vtk_react.html). [VTK.js: volume mapper](https://kitware.github.io/vtk-js/api/Rendering_Core_VolumeMapper.html).

The renderer uses a regional equirectangular coordinate system in kilometres, with depth multiplied by a visible exaggeration factor. This is a regional scientific view, not a global geodetic globe. Natural Earth coastline v5.1.2 supplies geographic context and an Indian Ocean overview. It does not supply bathymetry or change the model's wet-cell mask. Natural Earth data are public domain. [Natural Earth: terms of use](https://www.naturalearthdata.com/about/terms-of-use/).

The full-depth view and upper-500-m view are resampled independently from original bracketing source cells. The upper view dedicates more samples to the shallow interval; it does not manufacture native resolution. Display coordinates retain precision, while scalar display values round to five decimals. Profile comparisons and physical diagnostics continue to sample the source grid independently of the visual settings.

Nearest-neighbor texture sampling prevents missing-value sentinels from blending into wet values. Isosurfaces skip cells touching missing data and reject degenerate triangles. The synthetic demonstration still has a deliberately simplified analytical land mask. High-quality rendering does not make that mask an authoritative coastline.

## Larger archives and bounded rendering

The scientific API supports administrator-mounted immutable CF time archives. Files are hash-verified and combined only when spatial grids and variables agree and timestamps do not overlap. Registration reads metadata; scientific arrays stay lazy. Geographic region controls concentrate the display grid on a selected area, and the detailed setting requests up to 64 × 64 × 96 samples. Neither changes native resolution. Timestamp labels are bounded while every frame remains available through the slider.

The browser receives versioned float32 display packets with explicit missing values, validated dimensions and axes. Server and browser frame caches have memory budgets, and excess scientific requests receive a retry response instead of entering an unlimited queue. Native scientific exports retain their own precision. These mechanisms remain process-local; distributed ingestion and service failover require further infrastructure work.

A six-file synthetic archive contains a 24 × 64 × 512 × 512 scalar field: 1.5 GiB logically, about 108 MB compressed on disk. One local measurement produced 64 × 64 × 96 regional frames in a median 0.235 seconds across three uncached reads, with a process peak around 304 MiB. Values matched the known affine field within 0.00002°C. This is a bounded single-process test, not a real forecast accuracy, GPU frame-rate or simultaneous-user benchmark. The larger archive is available only on the API-connected local review; it is not bundled into the hosted demonstration.

## What the moving current paths mean

Streamlines integrate the displayed eastward and northward velocities with RK4 in physical geographic units at a fixed depth and frozen timestamp. Zonal angular motion includes the cosine-of-latitude factor. Integration is bounded by a 120-hour default horizon, a 3,600-second maximum step, a local quarter-cell displacement cap and a 2,048-step budget. Every RK4 stage checks support; paths stop at masks, domain boundaries, stagnation or the integration limit.

RK4 and grid-aware velocity treatment are established ocean-particle methods. Ocean3D's implementation is its own bounded frozen-field inspection aid; it is not an OceanParcels simulation. [Delandmeter and van Sebille, 2019: Parcels v2.0](https://gmd.copernicus.org/articles/12/3571/2019/index.html). [OceanParcels: geographic unit conversion](https://docs.oceanparcels.org/en/latest/examples/tutorial_unitconverters.html).

Animated dots accelerate display time by ×10,800. There is no inferred vertical velocity, diffusion, wind forcing or time-evolving advection. These curves are not pollutant forecasts, rescue trajectories or validated Lagrangian pathlines. The real temperature/salinity subset has no current components, so its circulation controls are unavailable. The synthetic current case remains clearly labeled.

## Interoperability and deployment

The local scientific API exports a vertical column as CoverageJSON and a bounded, exact-time native-grid subset as CF-described NetCDF. CoverageJSON output is checked against the official schema. CoverageJSON is an OGC Community Standard; this encoding does not by itself make the API OGC EDR conformant. [OGC: CoverageJSON 1.0, published 2023](https://docs.ogc.org/cs/21-069r2/21-069r2.html). [OGC: official CoverageJSON schema](https://schemas.opengis.net/covjson/1.0/coveragejson.json). [OGC: Environmental Data Retrieval API](https://docs.ogc.org/is/19-086r6/19-086r6.html).

The hosted workbench serves reproducible bundled cases. It does not run Python ingestion or give the hosted page access to private networks. The self-hosted service supports validated uploads, hash-based provenance, persisted imports, bounded operations and an optional bearer-token gate. Organizational authentication should sit at the reverse proxy; secrets must not be placed in browser code.

The scientific API implements WMS 1.3.0 GetCapabilities, GetMap and GetFeatureInfo, including the different axis orders of EPSG:4326 and CRS:84. WCS 1.0.0 capabilities, descriptions and GetCoverage expose each variable/native depth as a NetCDF coverage at an exact timestamp. It advertises no interpolation and rejects reprojection/resampling. Actual capability, description and WMS error responses pass the official OGC XML schemas; this is targeted validation, not complete conformance certification. The Data catalog provides usable service links. [OGC WMS](https://www.ogc.org/standards/wms/). [OGC WCS](https://www.ogc.org/standards/wcs/).

CF instrument imports preserve source positions, timestamps, mission membership and explicitly mapped quality flags. In-situ temperature requires colocated salinity and is converted with GSW while retaining the source values. Unknown quality remains excluded. An administrator variable manifest adds canonical scalar fields such as dissolved oxygen across ingestion, the catalog, rendering and exports. A hash-verified inbox command uses idempotent uploads and receipts for repeatable ingestion. These mechanisms accept new data; they do not establish a live connection to INCOIS sensors. [CF 1.12 discrete sampling geometries](https://cfconventions.org/Data/cf-conventions/cf-conventions-1.12/cf-conventions.html#discrete-sampling-geometries).

The regional implementation serializes native NetCDF work and uses bounded caches. Production integration still needs reviewed upstream subsetting/regridding, object-store chunks, queued conversion jobs, quotas, operational identity controls and measurements on representative INCOIS workloads. The Docker engine was unavailable for runtime validation. OPeNDAP serving is not implemented; the existing REST API fulfills the brief's REST/OPeNDAP alternative.

## Classroom and public outreach

The Learn tab offers four lessons directly coupled to the 3D Explorer: water-column depth, isosurfaces, currents and observation quality. Each lesson changes the working scene and includes an interpretation question with immediate feedback. Learners inspect colors against numerical units, distinguish a thermal surface from a material wall, and learn why frozen current lines are not rescue trajectories. All classroom data are explicitly synthetic. The classroom works in the bundled frontend, while imports and standards services require the scientific API. Usability with students and forecasters remains to be evaluated.

## How to present and evaluate the solution

Start with INCOIS · Bay of Bengal: reveal the volume, move both intersecting planes, switch monthly frames, and inspect spread alongside native observation support. Then use Water-column structure for the synthetic diagnostics and Real current circulation for the separate three-frame HYCOM velocity case. Explain that its animated paths use a frozen field and are not drift forecasts. Real-data validation opens the separate HYCOM–Argo case with 1,001 matched levels and a rejected cast. Finish with evidence export and source metadata.

The evaluation target is better scientific decisions with less manual work. Run timed tasks with forecasters or oceanographers: detect a temperature-definition mismatch, identify a rejected cast, distinguish unsupported coverage from low model error, reproduce a metric, and inspect a mixed-layer estimate. Compare task completion time and error rate with their current workflow. Do not replace this assessment with screenshots or an unsupported novelty score.

Software checks cover analytical 4D fields, exact wet nodes next to missing cells, singleton time axes, native-grid exports, schema validation, threshold definitions, real-file regression, geographic RK4 convergence and isosurface geometry. Browser checks must also cover interaction, mobile layout, stale-frame labeling and the bundled-data path. Measured timings should name their hardware and dataset; small regional results cannot establish global performance.

Before claiming operational readiness, obtain INCOIS acceptance criteria and authorized datasets, validate over independent casts and seasons, review every adapter's scientific semantics, establish storage/concurrency targets and test deployment failure recovery. These are concrete completion criteria for the next engineering phase, not features claimed as finished here.


Research & methods now includes a timed three-task recorder with pseudonymous participant codes, developer-practice labeling and local JSON export. Responses remain unscored until an assessor applies the documented rubric. The paired-analysis command excludes practice and unscored trials; no actual forecaster benefit is claimed. The public Argo table overlay explicitly uses its raw channel with retained QC and GSW conversion; the adjusted-only GDAC policy described above belongs to the separate GDAC adapter.
