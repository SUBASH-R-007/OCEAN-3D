# Validation record — 7 September 2026

This record describes executed checks on the delivered regional prototype. It does not certify operational readiness or independent forecast skill.

For subsequent changes, see the [8 September validation record](VALIDATION_2026-09-08.md), including the latest web deployment checks and [institutional deployment guide](DEPLOYMENT.md). Counts below describe the earlier 7 September run.

## Scientific and API tests

**65 backend tests passed** in the final complete suite (50.38 s). Tests cover analytical 4D interpolation, masked corners and exact wet nodes, unit/coordinate normalization, singleton time, time-gap bounds, QC/missing exclusions, empty metrics, transects, imports and persistence, authentication, MLD/BLT definitions, GSW density, upper-ocean sampling, official CoverageJSON schema and native NetCDF roundtrip. Six INCOIS tests verify native values/masks, metadata rejection, monthly-gap rejection, integer counts, dense-display equivalence and truthful source-specific exports. Two new Ocean lab tests compare every native temperature/count element in the browser packet against NetCDF and verify the relief source hash, pixel-center registration, finite values and range.

The retrieved real files are regression fixtures. The good Argo cast has 1,001 QC-1 matched levels and temperature RMSE 0.655267028998°C with model-minus-observation bias +0.105452344575°C. The rejected cast has 511 excluded temperature levels because adjusted salinity is missing/bad; no raw fallback is allowed. A separate BGC test verifies parameter mode overriding profile mode and rejection of unsupported CHLA units.

The actual running API also returned a schema-valid real-case CoverageJSON column and a readable CF-1.10-described NetCDF subset with dimensions time=1, depth=12, latitude=13, longitude=7. API media types, attachments, bounds and invalid requests were exercised.

**22 frontend numerical/state tests passed.** They include analytical geographic zonal displacement, RK4 convergence in a spatially varying field, missing/boundary/stagnation handling, component-grid mismatch and integration budget, coastline clipping, isosurface geometry including exact-threshold vertices and masks, view-state sanitation, color/log bounds, affine intersecting sections, masked faces, exact boundary sections and unit surface normals. Five new tests cover first downward crossings and inversions, missing/gap censorship, paired-change sign and support minima, bilinear geometry with preserved holes, and depth-lens continuity/monotonicity.

## Larger-archive extension

Twelve new backend cases verify lazy archive registration without scientific-array execution, exact time-file concatenation, geographic subsets and masks, checksum/grid/time/path/ID rejection, oversized physical-chunk guards, binary/JSON agreement, byte-budget eviction, request admission, responsive health during slow import parsing, and OGC metadata budgets. Four new frontend cases verify binary decoding and malformed packet rejection, cache accounting/eviction, saved geographic bounds and bounded timestamp labels. Type checking and authored-code lint passed; only explanatory JSX copy changed afterward, and both final production builds passed.

The on-disk synthetic archive contains 24 times × 64 depths × 512 latitudes × 512 longitudes: 1,610,612,736 logical scalar bytes and 107,712,333 compressed file bytes across six files. A separate measurement process peaked at 318,763,008 resident bytes. Three sequential model reads produced a regional median of 0.235 s and full-domain median of 0.307 s for 64 × 64 × 96 displays. Each selected 147,456 source cells from a 16,777,216-cell frame. Maximum analytical error was below 0.000007°C. Hardware, source fingerprint, sizes, timings and limitations are in [the reproducible record](benchmarks/scale-2026-09-07.json) and [scaling guide](SCALING.md).

A real loopback burst of 12 requests admitted six and returned six 503 responses with Retry-After: 2. All six later retries succeeded. Eight health checks completed in 6–68 ms. The cache held 4,531,296 encoded bytes afterward, below its 64 MiB budget. This is one capacity-control exercise, not sustained concurrent-user acceptance; [raw result](benchmarks/capacity-2026-09-07.json).

Browser testing exercised mounted-archive selection, a 80–90°E/5–20°N subset, detailed 64 × 64 × 96 frames, the upper-500-m window, rejection of a reversed region, full-domain restoration and the final timestamp at step 24/24. Page-scoped evidence confirmed exact requested bounds and 147,456 selected source cells. Desktop available/content widths were both 1,425 px at 1440×1050; phone widths were both 375 px at 390×844. One canvas and five timeline labels remained, with no inspected warnings/errors. The archive review caught and fixed an overflowing long timeline and a cramped tablet header. Viewport overrides were restored.

The final packaged Worker preview rendered the original INCOIS bundled frame with 54,200 valid samples, one canvas and no document overflow or inspected warnings/errors. It explained why regional requests need the scientific API, and the new archive-methods section appeared in Research & methods. The four actual OGC response XMLs were re-exported and revalidated against official XSDs after service-budget changes. Native OS download completion, GPU frame-rate/endurance, all-device accessibility, container runtime and distributed service failover remain unverified.

## Instrument, interoperability and classroom extension

Eight additional backend tests verify native CF profiles and moving-mission membership, exact source samples, explicit QC mapping, malformed metadata rejection, indexed/incomplete representations, in-situ GSW conversion with salinity QC, variable-plugin normalization/render packets/NetCDF, atomic registration conflicts, idempotent imports and restart restoration, WMS axis order and native sampling, null feature information, service exceptions and WCS native-grid roundtrip. Two additional frontend tests cover timestamp-ordered mission joins with gap/platform/seam boundaries and catalog-authorized saved plugin variables.

The actual WMS capabilities, WCS capabilities, WCS description and WMS exception responses pass the official OGC XSDs. Eleven official OGC/W3C schema files and their URLs/hashes are cached under `data/schemas/ogc`. The validation script uses lxml 6.1.1 from the bundled validation environment; the scientific runtime gained no dependency. These checks are narrower than full TEAM Engine certification.

The live ready-manifest inbox check imported a four-cast synthetic mission, then returned `already imported` on a second run. The browser file chooser uploaded the same native CF file, returned its timestamped profile chart with 6/7 matched levels and one QC rejection, and showed all four cast markers. After browser SHA-256 idempotency was added, repeating the form upload reused the original mission ID and chose model frame index 2 nearest the cast date. A temporary duplicate created during the earlier form test was removed; the single training mission remains available locally. Its values derive from the analytic fixture, so its zero residual is not evidence of observational skill.

The final bundled Worker preview also rendered the current lesson with 48 streamlines and no inspected warning/error logs. A missing classroom palette was corrected with a selectable blue–neutral–red diverging scale; the frontend suite, type check, lint and both production builds were rerun successfully.

Browser review exercised lesson selection, wrong/correct-answer feedback, isosurface preset, the current lesson with 48 displayed frozen-field streamlines, instrument selection, live service dataset/depth selectors and an INCOIS 100-m WMS image. The phone check found overflow from the fifth navigation tab; wrapping and explicit row heights fixed both overflow and overlapping rows. Classroom and service pages then measured 375 px content width at a 390×844 viewport (375 px available after scrollbar), with all tabs inside the header. The viewport override was restored. Native operating-system WCS download completion and full accessibility/device certification are not claimed.

## Ocean lab rendering and data

The new default view combines NOAA ETOPO 2022 numeric relief (50,600 vertices from a 0.1° extract) with native INCOIS thermal surfaces. The relief packet is 921,155 bytes; the exact native temperature/count packet is 488,785 bytes. Source hashes, acquisition details, algorithms and prior-art boundaries are documented in OCEAN_LAB_NOVELTY.md. The runtime stack is retained; Pillow 12.3.0 is an optional offline GeoTIFF preparation dependency.

July minus May at 20°C yields 172 paired native columns, an unweighted median of approximately −0.3 m and seven pairs with local observations at both crossing brackets. The largest absolute change is −45.9 m at 83.5°E, 10.5°N: May 139.6 m (125–150 m bracket) versus July 93.7 m (75–100 m bracket), with zero local observations at both bracket minima. Enabling the local-observation filter and inspecting its largest change selects 82.5°E, 6.5°N: −24.5 m, with local-count minima of one and three. These are changes in monthly objective analyses, not independently measured water motion or forecast skill.

Browser QA exercised thermal layers, threshold and month changes, source-support filtering, largest-change selection, native-grid selection, direct 3D picking, cross-section visibility and its 2–32°C legend, missing-column feedback, depth-lens/peel controls and source-bracket profiles. An unavailable column at 79.5°E, 22.5°N retained null results. Switching to Explorer retained 1,001 matched levels and disposed the hidden atlas canvas. The page-scoped WebMCP evidence reader followed the active view without stale Explorer metrics.

Final production review included 1440×1050 desktop and 390×844 phone layouts, automatic orbit, pointer drag stopping orbit, reset camera and uniform-35× basin relief. After responsive resizing settled, mobile content and available document width were both 375 px, with one atlas canvas. Thermal views explicitly label their piecewise depth scale. The final inspected browser warning/error log was empty. Native operating-system saving of the new investigation JSON, long-run GPU memory/frame-rate behavior and context-loss recovery were not verified.

## INCOIS integration and rendering extension

Official ERDDAP source: `incois_argo_mnt_McCreary`, May–July 2026, 79.5–95.5°E, 5.5–22.5°N, 24 depths 5–2000 m, 712,584 bytes. Original source SHA-256: `0eca3a4f7a98c0d7807da7e098fb4543ccc5d861a917fbb510d23f5cb02f870c`. Converted source SHA-256: `ed2eead8a518757638edd594ba8040f6f8e0421708520025c69dcf20c65f5a74`. Files, endpoint metadata and full reuse notice are preserved under `data/incois`.

The running API returned the new catalog, a 36×36×72 upper-ocean display with 54,200 supported samples in July, a schema-valid source-temperature CoverageJSON column without a false vocabulary identifier, and a native salinity NetCDF subset (1×14×18×17). Density diagnostics returned the expected 422 because the source lacks confirmed potential temperature. Direct source values and masks match the converted dataset. Display interpolation matches sampling of original source brackets, including missing cells.

Browser checks covered the official INCOIS journey, detail volume rendering, intersecting sections, boundary plane positions, top/front/reset cameras, lit isosurface and out-of-range empty feedback, temperature-spread selection, May/June/July frame selection, mobile controls and one scene canvas. Switching back to HYCOM retained 1,001 matched levels; switching to INCOIS removed the stale comparison panel. Native support updated to 14% in May and 23% in July. Desktop 1440×1000 and mobile 390×844 were inspected; horizontal document overflow was absent. Browser review exposed and fixed a cramped two-row mode control and a mobile hint alignment issue. Inspected current renderer logs contained no errors or warnings.

The portable and Worker production builds passed. An initial Worker build encountered a Windows file lock from the running review helper; stopping that owned helper resolved it. No code or TLS verification bypass was used. GODAS/IGORA LAS catalogues were accessible but data requests timed out; the integrated INCOIS source is the successful ERDDAP Argo product. Monthly data are a bundled snapshot, not a live connection.

Upstream warnings remain: Starlette/httpx and anyio deprecations, and a NumPy extension-size warning during a NetCDF-related import. Tested numerical and file operations passed. Validate the pinned binary stack on the target deployment platform; this session does not establish that every scientific binary combination is compatible.

## Production builds

TypeScript type checking and authored-code lint passed. Both the portable Vite frontend build and the Vinext/Worker production build passed for the final source. npm audit reported **0 vulnerabilities**; no package changes followed that audit. This is a point-in-time dependency check, not a security certification.

Measured final portable build: main JS 157.10 kB gzip; lazy Ocean lab UI 7.22 kB; atlas renderer 11.45 kB; shared VTK/section module 203.08 kB; existing Explorer renderer 111.99 kB. VTK remains a substantial dependency. Vite/Vinext emitted nonfatal large-chunk and future JSON-import-loader warnings. Worker output was run locally with Wrangler and the bundled-data workflow was checked in the browser.

The release archive `tmp/ocean3d-site-scale.tar.gz` contains the Worker entry point, hosting manifest, public assets and the existing bundled scientific snapshots, including the native INCOIS thermal packet, NOAA relief and synthetic CF glider example. It was validated locally: 200 entries, 10,174,772 bytes, SHA-256 `b476165cc2a94094b918188d871d35b51b2f1ad2098fad3537c807099971972b`. No dependencies, Git directory, environment files or large benchmark archive are included. The exact frontend source commit is `266adee370be09ab6b71c4c7279d9c619049c5f6` in the isolated Sites source repository; the user's root Git history was not modified. Backend code, original source datasets and the 1.5 GiB logical scale fixture remain local.

## Browser checks actually performed

The user explicitly authorized thorough browser testing. Tests used the Codex in-app browser, including desktop 1440×1000 and phone 390×844 viewport settings, restored after responsive checks.

The final INCOIS production build was rechecked after packaging: source panel and download links, intersecting sections, monthly labels and the research dossier rendered correctly. At a 390 px viewport, the available document width and content width were both 375 px; the scene hint stayed within the viewport and one scene canvas remained. The final inspected warning/error log was empty. The viewport override was restored after review.

| Workflow | Observed result |
| --- | --- |
| Volume, cutaway and isosurface | Rendered in WebGL; cutaway changes visible; absent isovalue shows explanatory message |
| Orbit and time | Pointer rotation works; marker positions retain the same relative geometry across time changes; one scene canvas remains |
| Slice and depth | Visible slice and actual nearest displayed depth label agree; keyboard End/Home controls update values |
| Render quality and exaggeration | Fine sampling and 1× exaggeration accepted; ray-sample budget adjusted to avoid observed excessive-step warnings |
| Circulation | 48 frozen-field RK4 streamlines rendered in synthetic case, including bundled production mode; fixed-depth/time assumptions visible |
| Real-data comparison | 1,001/1,001 matched levels, displayed RMSE 0.66°C and bias +0.11°C |
| Rejected real cast | 0/511 matched, 511 exclusions, missing adjusted-salinity explanation and null metrics |
| QC policy | Strict 11/13 becomes lenient 12/13 on the analytical cast |
| Coverage without support | Zero eligible profiles and explicit no-support message; no invented confidence score |
| Physics | Real model density MLD 33.1 m, observed MLD 55.8 m, model thermal depth 56.3 m and signed separation 11.4 m; distinct timestamps/brackets shown |
| Time playback | Play becomes Pause and advances from first to later frames; pausing works |
| Valid CSV upload | Test cast appears, is selectable and yields 1/1 matched level |
| Corrupt NetCDF upload | Rejected before registry insertion; parser message then improved and retested through API |
| Mobile | No horizontal page overflow at 390 px; scientific controls expand/collapse; geography, scene and research dossier remain usable |
| Saved view | Reload restores the selected real case and depth window after catalog loading |
| Research dossier | Primary-source links, contents, real data, methods and limitations render on desktop and phone |
| WebMCP evidence reader | Registered name/schema/annotations checked; valid empty input returns current evidence; unknown fields reject intentionally |

Browser automation did not confirm operating-system file saving: its download event timed out for paired CSV; the direct CoverageJSON download action returned without error, and export payloads independently passed live API/schema/NetCDF checks. The helper now attaches its download anchor and allows 30 seconds before object-URL release for embedded-browser handoff. Native fullscreen and clipboard copy completion were not confirmed by the in-app browser. Do not report those platform-dependent actions as passed. Browser save-view storage was verified independently.

No final-production browser error was observed in the inspected log. Historical development ray-step warnings led to the sample-distance budget fix; those historical entries remain in the tool log. This is not a measured long-run GPU memory, frame-rate or context-loss recovery benchmark.

## Bounded performance measurement

Windows, Intel Core i7-13650HX, Python 3.11, in-memory analytical fixture, five direct Python repetitions, excluding HTTP, network and GPU costs:

| Operation | Median | Maximum | JSON bytes | Gzip bytes |
| --- | ---: | ---: | ---: | ---: |
| Display temperature volume, target resolution 36 | 9.62 ms | 13.71 ms | 248,039 | 85,254 |
| One strict profile comparison | 1.15 ms | 1.74 ms | 2,728 | 1,094 |

Source dimensions: 6 times × 25 depths × 36 latitudes × 34 longitudes. Reproduce with `python -m scripts.benchmark`. These results do not establish global archive scale, concurrent service capacity or low-power GPU performance.

## Deployment and remaining validation

Docker Compose configuration passes validation. Image builds and container runtime could not be verified because the Docker Desktop Linux engine pipe is absent. The provided Docker configuration remains untested at runtime.

The current Sites audience was read as **public**, with the user as owner. Automatic approval review rejected pushing updated source and bundled data because explicit authorization for that external destination was missing. No updated source was uploaded and no new version was published. The validated archive and local production preview are ready; source upload and public publishing await user approval. The existing live site still serves its prior version.

Remaining operational work: INCOIS operational forecast access and acceptance criteria beyond the included public monthly Argo analysis; reviewed curvilinear/sigma/staggered and additional sample-varying/pressure-only instrument adapters; independent assimilation-aware seasonal validation; production identity, quotas, storage and concurrency; full OGC conformance certification and OPeNDAP/EDR serving; container runtime, GPU recovery and broader accessibility/browser testing. A one-cast analysis, monthly objective analysis and synthetic fixture do not establish independent forecast skill.
