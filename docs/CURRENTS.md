# Real currents through the water column

The Explorer's **Real current circulation** journey opens a real FNMOC HYCOM ESPC-D V02 forecast subset. It includes eastward velocity, northward velocity, potential temperature and practical salinity on matching coordinates and valid times. The INCOIS analyses remain separately available.

## Source and scientific meaning

- Fixed forecast initialization: **6 September 2026, 12:00 UTC**.
- Valid times: **7 September 2026, 12:00, 15:00 and 18:00 UTC**; leads **24, 27 and 30 hours**.
- Source subset: **93 longitudes × 123 latitudes × 40 depths × 3 times**. Actual bounds are approximately **30.480–118.800°E, 29.480°S–29.080°N**.
- All published z levels from **0 to 5,000 m** are retained. Horizontal stride 12 produces approximately **0.96° longitude × 0.48° latitude** spacing in this subset. It is not a download of every original horizontal cell.
- The original NCSS NetCDF responses and SHA-256 hashes are preserved in `data/hycom/` and bundled for download. The manifest records the complete source requests. Current components remain exactly equal to the decoded source float32 values, including missing masks.
- HYCOM supplies in-situ temperature. GSW converts it to potential temperature at 0 dbar using the matching salinity, depth and geographic coordinates. The original temperature remains available in the source NetCDF.
- These are model forecasts, not instrument measurements or a continuously synchronized feed. No vertical velocity is supplied or inferred.

The public [forecast-run catalogue](https://tds.hycom.org/thredds/catalog/FMRC_ESPC-D-V02_uv3z/runs/catalog.html) identifies each initialization. The NCSS fixed-run subset omits the run coordinate; the manifest therefore identifies initialization from the explicitly selected THREDDS run URL. Template global `time_origin` attributes are not treated as the selected run. The acquisition pipeline rejects differing component coordinates, valid times, or explicit forecast initializations. This matters because the best-available velocity and scalar collections can come from different model runs despite having identical valid times.

## Rendering and inspection

1. Open **Explorer → Real current circulation**.
2. **Throughout the column** displays vectors at 6, 12 or 24 depth samples, or every depth of the bounded display grid. Layer sampling concentrates near the surface while retaining the deepest available level. A glyph budget limits horizontal sampling; the scene reports the displayed vector and depth counts.
3. **Selected depth** moves the vector plane through the full available column, including 5,000 m. Missing or stagnant samples produce no directional glyph.
4. **Direction arrows · speed by color** gives weak deep currents a visible direction without pretending their speed is greater. **Length and color by speed** preserves speed-proportional arrow lengths. The scene labels the length convention and speed colorbar. Regional projection correction is applied to eastward displacements.
5. **Animated streamlines** integrates the horizontal components with RK4, at one selected depth or six distributed depths. Each path holds its physical depth and timestamp fixed. Motion is accelerated for display; this is not a time-evolving particle forecast, and no vertical velocity or diffusion is invented.
6. The **Currents through depth** panel reports speed, eastward/northward components and direction towards, with a depth chart, valid time, initialization and forecast lead. It samples the bounded display grid and preserves missing gaps.
7. Volume, slice, isosurface, intersecting sections, region selection and time playback work with the new dataset. Temperature or salinity can be displayed with the same current overlay. Exported evidence includes actual u/v samples, depths, timestamps, source provenance and rendering conventions.

Uniform display-grid interpolation is separate from original source resolution. The source files and native-field NetCDF exports retain the available source depths and cells. Surface-only INCOIS products do not acquire fabricated subsurface currents.

## Reproduction and deployment

Run `python -m scripts.bootstrap_currents` from the repository root to prepare the preserved snapshot and browser packets. It reuses existing source files; new downloads use verified HTTPS, bounded request duration and a 32 MiB cap. Keep the API stopped if replacing an already registered dataset. The upstream rolling forecast catalogue can eventually remove a run; preserved source files keep this case inspectable when that happens.

The API verifies source and normalized-model checksums before registration. Native exports, binary volume transport and existing OGC endpoints apply to the new model. The Docker recipe includes its data directory. Browser-only deployments use the bundled three frames; the scientific API additionally supports regional requests and exports.

There is no new live-synchronization scheduler or vertical-current model in this change. The public Sites update remains subject to the existing pending source/data upload and publication authorization.
