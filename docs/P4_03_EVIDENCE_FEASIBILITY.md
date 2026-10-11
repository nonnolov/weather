# P4-03 Rainfall and flood evidence feasibility

## Goal

Determine whether forecast rainfall amount/duration can be paired with location-relevant historical rainfall and flood outcomes well enough to derive and validate a local trigger. Do not create thresholds or turn on user-facing flood-risk states during this audit.

## Official sources found

| Source | Useful evidence | Known limitation / check before integration |
| --- | --- | --- |
| HII rainfall telemetry (data.go.th/dataset/hii-rainfall) | Hourly and daily observed rainfall, station metadata, historical CSVs; Thaiwater Standard also documents time-range rainfall API queries. | Check station coverage, interval semantics, missing sentinels, terms, API credentials, and distance to app locations. Station rainfall is not the forecast at the user's point. |
| GISTDA recurring flood layer (data.go.th/dataset/disasters-01) | Spatial recurring-flood layer covering 2011-2023, queryable by coordinates or geometry. | Recurrence is spatial evidence, not event timestamp or severity; insufficient by itself to pair rainfall windows. |
| GISTDA Disaster Platform (data.go.th/dataset/flood-disaster-data) | Daily flood-area products and API-key access; current published coverage is nationwide. | Satellite flood areas are time-bounded observations, may not identify cause or street-scale flooding; verify API access and historical backfill. |
| HII water-event history (data.go.th/dataset/hydro-historical-report) | National flood/drought event records; public XLS/XLSX/PDF catalog, updated annually. | Confirm event dates, geocoding precision, source quality and duplicate/omitted events. |
| Bangkok Metropolitan Administration (BMA) | Official flood-prone point records; infrastructure page lists 737 risk points based on 2022 lessons; live road-flood monitoring exists. | Some public datasets are old (2021/2023); inspect actual files and live monitoring structure/freshness. Risk points are not the same as timestamped flood observations. |

## Audit steps and acceptance gates

1. Download/read schemas and sample records; document source URL, owner, license/access, last update, units, interval and quality flags.
2. For each candidate pilot area, spatially match saved user locations to available rainfall stations/grids and flood records. Record distance/coverage and reject unsupported matches.
3. Build a small historical pairing sample for 1/3/6/24-hour rainfall windows and flood/non-flood periods. Treat missing flood reports as unknown until source completeness is established.
4. Evaluate whether event counts and temporal/spatial precision support a threshold. Use chronological holdout; report counts, false-alarm rate and missed-event rate. If labels are inadequate, stop at rainfall exposure and keep risk `not_assessed`.
5. Only after a successful audit, propose a narrowly scoped P4-04 pilot and local thresholds for review. Nationwide availability must not be inferred from a pilot.

## Current result

Promising ingredients exist, especially HII hourly rain history and GISTDA/BMA flood-area or flood-point data, but no validation-ready joined training set has been confirmed. The next engineering step is schema/access inspection and a pilot-location coverage report, not deployment or risk-band activation.
