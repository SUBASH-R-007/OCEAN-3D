# Ocean3D advancement plan — 7 September 2026

Scope: fulfill SIH26067 with a defensible regional scientific workbench, advanced rendering and real-data evidence. The planning tool is unavailable; this file records progress.

Current revision: audited the larger-scale path and implemented immutable lazy archives, bounded chunks/metadata, regional display queries, float32 transport, memory-accounted caches, request admission and long-timeline controls. 65 backend tests and 22 frontend tests pass; the 1.5 GiB synthetic disk benchmark and 12-request capacity probe ran successfully. Final desktop/phone/bundled browser review and source packaging are complete. Public upload remains pending the earlier destination approval. Live INCOIS forecast feeds and institutional operational acceptance remain external dependencies.

Latest request: strengthen visual complexity and novelty. Reviewed the supplied problem text, both DOCX guides and the architecture explanation. Implemented Ocean lab with actual NOAA terrain, layered native thermal surfaces, a source-bracket change lens, direct 3D probing, geographic labels, a local-observation filter and investigation exports. Local implementation, documentation, desktop/mobile review, both production builds and release packaging are complete. All 45 backend and 16 frontend tests pass. Publishing remains subject to the existing unresolved external-upload approval.

Completed extension: integrated INCOIS's official May–July 2026 Argo objective-analysis subset, preserved its unspecified temperature convention, exposed source support and spread, and added intersecting 3D sections. The source adapter, geometry, exports and browser interactions passed validation, including 43 backend tests, 11 frontend tests and both production builds. Public publishing still requires the previously requested authorization.

1. **Complete:** primary-source research, two read-only research lanes, conflict reconciliation and bounded public data acquisition.
2. **Complete:** scientific diagnostics, strict adjusted-data handling, true source-bracket resampling, real case, persistent rendering, streamlines, depth window, exports and cited research dossier.
3. **Complete:** scientific suite, numerical geometry checks, both production builds, live API exports, desktop/mobile and bundled-production browser QA; actual limitations recorded in VALIDATION.md.
4. **Local work complete; publishing pending:** the Ocean lab release archive and final local production review are complete. The archive includes all 18 INCOIS frames, native thermal profiles/counts and NOAA terrain; its hash and isolated source commit are recorded in VALIDATION.md. Source upload and public publishing await explicit user approval after automatic review rejected the source push.

| Material decision | Evidence / implementation | Confidence and limits |
| --- | --- | --- |
| Retain stack | VTK official APIs and running volume/slice/isosurface UI | High for regional workbench; not a global scalability claim |
| MLD and barrier definitions | 2004/2007 original papers, GSW definitions, threshold tests | Definitions distinguished; TEOS barrier adaptation and policy gaps disclosed |
| Real data | Official INCOIS monthly analysis, HYCOM subset, good Argo cast and bad adjusted-salinity cast retrieved with hashes | INCOIS native masks and source definitions retained; real collocation demonstrated; independent skill not established |
| Current paths | Geographic RK4, masks, stopping reasons, analytical/convergence tests | Frozen fixed-depth streamlines; no vertical/time-evolving transport |
| Interchange | Official CoverageJSON schema and native NetCDF roundtrip | Encoding tested; WMS/WCS/EDR serving not claimed |
| Rendering responsiveness | Persistent context, lit volume/isosurface, two movable vertical sections, bounded caches, desktop/mobile UI checks | Regional prototype; display interpolation does not increase native scientific resolution; no measured global archive/concurrent GPU capacity |

Research stopped after source definitions, access, data compatibility and implementation choices were resolved; further general search would not change those decisions. Remaining unknowns are operational acceptance, assimilation independence and production workload requirements.
