# Instrument overlays: implementation and evidence

The Explorer now has the same **Instruments** inspector on every model, including INCOIS analyses and the HYCOM current case. **Source** retains the model-specific evidence. Clicking a marker switches to its profile; the instrument selector provides keyboard access and access to nearby casts. The **Real instrument overlays** journey opens the Indian Ocean with real observations enabled.

## Real observations included

| Source | Included observations | Measurements available |
| --- | --- | --- |
| Argo GDAC reference case | Two September 2023 Argo casts already retained with the reference model | Potential temperature and practical salinity; adjusted-channel QC retained |
| [IMOS/UWA Ningaloo SG152](https://research-repository.uwa.edu.au/en/datasets/imos-ocean-gliders-seaglider-deployment-in-western-australia-off--3/) | Four consecutive native casts, PROFILE 10–13, 7 September 2010, off Western Australia in the eastern Indian Ocean | Potential temperature, practical salinity and chlorophyll; native sample positions, depths, timestamps and phase |
| [GO-SHIP I09N 2025 / CCHDO](https://cchdo.ucsd.edu/cruise/325020250321) | Stations 8, 36, 64 and 88: 28 March, 6 April, 14 April and 21 April 2025 | Pressure-derived depth, potential temperature and practical salinity; original CTD values and WOCE flags retained |
| [INCOIS BGC-Argo 2902273 cycle 159](https://data-argo.ifremer.fr/dac/incois/2902273/profiles/SD2902273_159.nc) | 1 September 2023, Arabian Sea | Temperature and salinity pass strict QC at 995 levels. Chlorophyll has 58 adjusted QC-2 values, available only with the explicit probably-good policy; two bad chlorophyll values remain excluded |
| [AOML BGC-Argo 2903464 cycle 7](https://data-argo.ifremer.fr/dac/aoml/2903464/profiles/SD2903464_007.nc) | 1 September 2023, south of Sri Lanka | Temperature, salinity and chlorophyll each have 504 strict-QC eligible levels |

These are real historical observations. They are not simultaneous deployments or a live feed. Argo's [S-profile terminology](https://argo.ucsd.edu/data/data-faq/version-3-profile-files/) denotes merged core/BGC observations; these files are not simulated data. Existing analytic examples remain separately labelled and separated from real-model overlays.

## Scientific behavior

- **Independent observation variable:** inspecting chlorophyll does not change the displayed model current or temperature field. Missing model variables and incompatible temperature conventions leave the observed profile visible and provide an explicit comparison explanation.
- **Time and spatial support:** comparisons use native observation coordinates and timestamps, not the current display-frame timestamp. IMOS casts retain per-sample positions and times; the backend queries each sample. Unsupported locations, times, depths, missing cells and excessive model-time gaps are not extrapolated. No-match metrics remain empty.
- **Quality semantics:** the IMOS adapter maps named source meanings. Interpolated underwater positions (IMOS position flag 8) remain identified as estimates between navigation fixes. WOCE CTD flag 2 means acceptable measurement and maps to canonical good (1); uncalibrated, interpolated and despiked flags are not silently promoted. Argo parameter-specific adjusted/raw selection remains unchanged.
- **Temperature:** GSW converts in-situ temperature using source salinity, pressure and position. Original in-situ values and flags remain available. CTD depth derives from measured pressure and cast latitude. Neither the adapters nor UI equate INCOIS's unspecified analyzed-temperature convention with potential temperature.
- **Geometry:** markers use native cast positions in the scene's geographic transform. Leader lines retain the true anchor while labels are separated for selection. Glider trajectories use native underwater positions, with three-dimensional clipping against the display domain/depth window. Invalid-position gaps break paths. Vertical cast extents and charts retain their different meanings: a chart can show depths beyond the current display window.
- **Charts and exports:** rejected/missing readings break the plotted line. The SVG line uses accepted native values; up to 200 marker dots limit DOM work without resampling the line. CSV retains all source rows, including QC-excluded readings, with variable, unit, profile ID, sample timestamp/position, depth, source/canonical QC and available model residuals. JSON evidence includes source provenance and comparison state. Stale profile/model/QC responses cannot be displayed or exported as the current comparison.

## Ingestion, preservation and deployment

`backend/instrument_sources.py` adds `imos-glider` and `cchdo-ctd` adapters alongside the existing GDAC, CF profile and delimited-text adapters. Native uploads require bounded subsets of at most 200,000 samples/levels and retain the existing 50 MiB upload cap. They validate documented units, dimensions and QC metadata before registration and persist as NetCDF imports.

`python -m scripts.bootstrap_instruments` prepares the collection. Original remote NetCDF files are preserved in `data/instruments/`; native subsets retain every selected source sample and its mask. The manifest records full-source and subset hashes. A separately hashed normalized cache avoids repeatedly decoding NetCDF metadata at startup. Every source and cache hash is checked before the collection is loaded.

Browser-only builds contain per-profile observation packets and downloadable native subsets. Existing precomputed reference comparisons remain available. Other combinations display the observed profile with an explicit statement that a native model comparison is not bundled; the scientific API performs that comparison. No model values are inferred from the rendered image. Source terms, acknowledgements and hashes are exposed in the inspector and retained in the files. The API Docker recipe includes the instrument directory; Docker execution remains unverified in this environment.

## Validation on 8 September 2026

- Source-subset checks compare coordinates, values, timestamps, masks and QC arrays against original NetCDF with exact equality. Native conversion checks independently evaluate GSW formulas. BGC strict/lenient outcomes and moving-sample queries are tested.
- Eight instrument-specific tests pass across the targeted runs, including the final native-upload API and cache-tampering checks. The broader API/science/extension run passed 37 tests; its one failure was an incorrectly shaped test double, corrected before all seven original instrument tests passed. No remaining implementation failure is known from these checks.
- All 28 frontend scientific tests pass. New cases cover observation-only fallback, QC gaps, faithful CSV metadata, three-dimensional trajectory clipping and overlapping marker labels. Type checking and lint pass.
- The original repeated NetCDF-decoding path took about 22 seconds for this instrument collection. The checksum-verified normalized-cache path took 0.188 seconds on the same host. This measures collection loading, not total API startup or a deployment performance guarantee.
- Browser checks verified real Glider, CTD and BGC marker selection on INCOIS, independent chlorophyll inspection on HYCOM, explicit QC-2 selection yielding 58 INCOIS chlorophyll readings, preserved state across Source/Instruments tabs, and the CSV download action. Additional production/mobile results are recorded in the dated validation log.

This satisfies the instrument overlay and timestamped profile-inspection feature for the supported formats and included real cases. Arbitrary instrument vendor formats still need adapters; pressure-only generic CF layouts are not all supported by the specialized CCHDO adapter. Historical observations remain historical, and no operational validation or live synchronization is claimed.
