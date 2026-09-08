# Public INCOIS synchronization

The writable scientific service checks the official public INCOIS ERDDAP catalogue and acquires bounded, validated selections. This implements continuous **polling while the service runs**. Source timestamps, rather than successful HTTP requests, determine whether the scientific data is current. It does not grant access to restricted INCOIS forecast or sensor feeds.

## Configure and use

`start.ps1` and writable `compose.yaml` enable checks every six hours. Direct `python -m backend.server` defaults to disabled automatic checks; set `OCEAN_SYNC_ENABLED=true` and optionally `OCEAN_SYNC_INTERVAL=21600` before starting it. The interval accepts 3,600–604,800 seconds. A first start checks immediately; restart restores the last complete generation and resumes its saved next-check time. The service must remain running; this is not a desktop reminder or an operating-system startup installation.

Open **INCOIS sources → Source freshness** to inspect the last attempt, last publication, next check and per-product results. **Check INCOIS now** queues a background refresh; duplicate requests and retries within 60 seconds receive 409. Status is polled every ten seconds. **Load updated source catalogue** explicitly adopts a published revision without changing a scientist's active selection silently. Open a water-column product in 3D to load that generation into Explorer.

| Route | Behavior |
| --- | --- |
| `GET /api/sync/status` | Schedule, publication revision, product dates and failures |
| `POST /api/sync/run` | Queue one bounded refresh on the writable service; 202 accepted |
| `GET /api/incois/catalog` | Current published source catalogue |
| `GET /api/sync/snapshot/{revision}/{product}` | Immutable validated packet from a retained revision |

Existing API-token protection applies. Read-only replicas cannot synchronize; `compose.readonly.yaml` disables it. They may serve a previously prepared, immutable generation. Stop the writer before serving its files with read-only workers, or promote a separate verified copy. This is a single-writer service, not a distributed scheduling or snapshot-promotion system.

## Acquisition and scientific meaning

Each cycle refreshes catalogue metadata and native coordinate axes, then requests the latest bounded packet for every advertised product with a supported layout. As checked on 8 September 2026, this covers 16 public products: four water-column analyses, eleven surface/diagnostic products and the Indian Argo table. All published time indices remain available for bounded on-demand requests. It does not download the entire historical archive every cycle.

- Water-column analyses retain all native geographic cells and 24 depth levels for up to the latest three source frames. Their original NetCDF bytes and normalized model are retained. Their source temperature convention is unspecified; it remains distinct from potential temperature.
- Surface packets use every listed variable at the latest timestamp, bounded by the existing display sampling limit. Winds remain atmospheric winds; surface satellite products do not acquire invented ocean depths.
- The Indian Argo table uses the latest 24 hours relative to its published end date. Raw and adjusted values and QC remain in the source packet. The 3D overlay explicitly uses the raw channel: GSW converts in-situ temperature using raw salinity and pressure, preserves QC and original values, and never silently substitutes adjusted data. Missing position QC and DATA_MODE remain disclosed. Unknown/rejected flags follow the existing inspector policy.
- A newly advertised observation layout without a reviewed adapter is metadata-only. Unavailable or unsupported products are reported individually, not rendered as another source.

The implementation follows ERDDAP's [native griddap selection and NetCDF response contract](https://coastwatch.pfeg.noaa.gov/erddap/griddap/documentation.html). The allowlisted source is the [official INCOIS ERDDAP catalogue](https://erddap.incois.gov.in/erddap/info/index.html). Requests have verified HTTPS, a 45-second curl deadline, size limits and explicit coordinate bounds. Metadata is limited to 64 products and 2 MiB per response; existing scientific downloads are bounded to 32 MiB.

## Publication, failure and persistence

Generations live under `OCEAN_DATA_DIR/.sync/revisions/<revision>`; the existing persisted import volume therefore contains synchronized data too. SHA-256 manifests verify packets, axes, metadata and model files before publication and at restoration. The current pointer is atomically replaced before the serving generation changes under the scientific lock. A failed pointer write leaves the serving data untouched; a rejected publication restores the prior pointer. Checksums detect corruption, not authenticity against an administrator who can rewrite both the files and manifest.

A catalogue/axis failure retains the previous generation. A single product failure retains its previous usable packet/model when available, with the original retrieval date and an explicit error; it does not relabel old observations as new ones. A product without previous usable data remains unavailable. Full and partial publication are separate statuses. A failure retries on the normal interval or an explicit manual request; no exponential retry or external notification service is claimed.

Requests carry catalogue revisions so time/depth indices use the corresponding axes. Expired revisions fail explicitly and ask the browser to reload. The service retains three complete generations during a process lifetime, clears encoded model frames on publication, and caps the loaded model catalogue at 32. Restart restores only the current generation. Local sync storage is checked against a 1 GiB budget before each cycle; source acquisition uses the existing separate 512 MiB cache. These are bounded prototype policies, not archival retention guarantees. Maintain operator backups and disk monitoring.

## Observed source availability

The first actual cycle completed in 35.31 seconds on 8 September 2026 and acquired all 16 products. Restart restored 14 models and 29 observation records with zero restoration errors and preserved the next scheduled check. The latest 10-day analysis date was **30 July 2026**, monthly analysis date **15 July 2026**, and Indian Argo table date **23 April 2025**. Other surface products also ended before the check date. These are successful public-source acquisitions of historical publications, not a current operational forecast feed. [Recorded first-cycle and restart evidence](benchmarks/incois-sync-2026-09-08.json).

The fixed HYCOM and instrument research cases remain separate snapshots. This scheduler does not refresh HYCOM, arbitrary glider missions, CTD/BGC portals or institutional message streams. Their documented adapters and inbox command remain available for authorized integration.
