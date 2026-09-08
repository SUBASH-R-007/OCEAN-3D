# Ocean lab — rendering and novelty review

7 September 2026. This is the second substantial rendering revision, prompted by the team's request to move beyond a simple volume block.

## What the earlier documents establish

The supplied SIH26067 text, Problem Breakdown, Solution/Dataflow Guide and System Architecture explanation consistently prioritize depth-resolved fields, geographically aligned observations, trustworthy comparisons, browser interaction and outreach. Their proposed technologies and implementation advice are reference material, not independent user instructions. The existing Explorer already implements much of this baseline. Adding another palette or an invented AI prediction would not address the visual or analytical gap.

The previous view lacked physical basin geometry and made users infer changes by switching frames. Its regional rectangular bounds were visually dominant. The new **Ocean lab** opens on a geographic terrain scene and connects a 3D change directly to its native profiles and source support. Explorer remains available for GPU volumes, scalar slices, full-depth data, instrument comparisons and TEOS-10 diagnostics.

## Concrete contribution

| Contribution | What the user can do | What is new in this project | Boundary |
| --- | --- | --- | --- |
| Geographic thermal architecture | Orbit real terrain; reveal 28°C, 24°C and 20°C layers; toggle each layer and inspect a vertical curtain | A co-registered basin and thermal scene replaces an isolated rectangular data block as the opening experience | Uses established surface rendering; does not invent new temperature resolution |
| Native-bracket change lens | Compare isotherm depth between two actual INCOIS months, inspect the largest change, and probe any native column | Every displayed change leads to its two source brackets and monthly profiles | Change in an analyzed field, not tracked water motion, heat content, cause attribution or a forecast |
| Source-support filtering | Retain only pairs with local observations at both crossing brackets | The scene visibly collapses to eligible native columns; isolated pairs remain as points/connectors rather than fabricated continuous surfaces | Local presence is a coverage criterion, not a validated accuracy/confidence threshold |
| Reproducible investigation | Export source hashes, threshold, periods, location, native profiles/counts, crossing results and display settings | The visual claim is an inspectable data record | This release exports an investigation; it does not import the record automatically |

These are integration and interaction contributions. Isosurfaces, threshold crossings, ETOPO bathymetry and Argo objective analysis are established prior art. No claim of a world-first ocean platform or newly invented physical model is justified. Test the workflow with oceanographers: compare task completion time, source-definition mistakes and incorrect confidence judgments against the previous Explorer.

## Data and method

INCOIS: the already verified `incois_argo_mnt_McCreary` monthly subset, May–July 2026; 17 longitudes × 18 latitudes × 24 depths. `scripts/export_thermal_atlas.py` verifies the original source hash and exports exact decoded T_ANALYZED, T_BOXOBS and T_ROIOBS values. No interpolated display volume is used for the calculations.

For each native column and threshold, find the first shallow-to-deep crossing from warmer to cooler. If the shallowest value is already colder, no crossing depth is assigned. A missing level before a crossing, a non-increasing depth axis or a depth interval over 150 m censors the result. Within a valid bracket, linear interpolation yields a depth. Exact shallowest-level equality returns that level. This policy measures a **first downward crossing**, not all disconnected isotherm branches and not a definition of thermocline depth.

Depth change = selected-month crossing depth minus reference-month crossing depth. Positive means deeper. Both crossings must exist. The domain median is over paired native columns, unweighted by area; it always describes all pairs even when the visual support filter is enabled. Counts at a crossing are the minimum of the two native bracket counts. A locally supported pair requires positive local counts in both months. Counts cannot be summed to unique floats.

Rendering tessellates only complete native quadrilaterals, with bilinear geometric interpolation. Source holes remain open. In local-only mode, all four corners must meet the filter to emit a face; isolated pairs are rendered as endpoint dots and depth connectors. The map and 3D change field share a blue–neutral–orange scale saturated at ±50 m. Source metrics remain unclamped. The reference month is a sparse native-grid wireframe; the selected month is the colored surface. The layer view applies staggered clipping: base peel plus 36, 18 and 0 percentage points for 28°C, 24°C and 20°C, capped at 85%; it never offsets layer depths.

## Terrain and depth scale

NOAA ETOPO 2022 ice-surface elevation is retrieved as a numeric float GeoTIFF from NOAA's official Grid Extract service. The requested area is 76–99°E, 3–25°N, with 230 × 220 pixels (0.1°). The underlying product is 15 arc-seconds; the requested extract is coarser. GeoTIFF pixel-is-area registration is validated and converted to pixel centers (76.05–98.95°E, 3.05–24.95°N). Rows are reversed to an ascending latitude axis. There are 50,600 finite numeric elevations, from −4,656.73 to +2,912.55 m. The raster SHA-256 is `2aa7b86b48a24482f2d240d356b32a06aa4312b406806ad4917e754f6111585b`.

In thermal views, the upper 500 m uses an adjustable 400–1,600× depth lens, default 1,000×; deeper terrain and land use 35×. The transform is continuous at 500 m and changes slope there. It is applied equally to all geometry at a given depth. Basin-relief mode uses uniform 35×. This deliberate distortion is labeled in the scene. It makes shallow structures legible but must not be interpreted as undistorted slopes or aspect ratios. ETOPO is independent geographic context; it neither fills nor changes the INCOIS mask.

NOAA citation: NOAA National Centers for Environmental Information (2022), ETOPO 2022 15 Arc-Second Global Relief Model, DOI [10.25921/fd45-gt74](https://doi.org/10.25921/fd45-gt74), accessed 7 September 2026. [Product](https://www.ncei.noaa.gov/products/etopo-global-relief-model), [metadata and CC0 terms](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ngdc.mgg.dem%3Aetopo_2022), [official extraction configuration](https://www.ncei.noaa.gov/maps/grid-extract/js/app/datasets.json). These data are geographic context, not navigational bathymetry.

## Reproduce

Run `python -m scripts.export_thermal_atlas` after acquiring the INCOIS files. For terrain acquisition, install the optional `requirements-data.txt` (Pillow 12.3.0), then run `python -m scripts.bootstrap_relief`. Original GeoTIFF and provenance live in `data/geography`; browser packets live in `web/public/geography/bay-relief.json` and `web/public/demo/incois-bob/thermal-structure.json`.

Numerical tests cover analytic crossings, inversions, missing levels, gaps, change sign, support minima, median, bilinear geometry, preserved holes and the continuous depth transform. Source-packet tests compare every temperature/count element to NetCDF and verify terrain registration/hash. Browser results and actual limitations are recorded in VALIDATION.md.
