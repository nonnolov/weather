# Nearby measured-rain reference and point reports

## Scope and result

Current system location was resolved in a short read-only production transaction:
Saen Suk, Mueang Chonburi. Exact current-user coordinates, recipient identifiers,
tokens and connection strings remain outside this report and git.

The public ThaiWater page's published JavaScript identifies these unauthenticated
read endpoints; they were fetched without login, purchases or service creation:

- https://api-v3.thaiwater.net/api/v1/thaiwater30/frontend/shared/station_all?province_code=20
- https://api-v3.thaiwater.net/api/v1/thaiwater30/public/rain_24h
- https://api-v3.thaiwater.net/api/v1/thaiwater30/public/rain_24h_graph?station_id=1116457

Station candidates use great-circle distance from the existing system location,
not travel distance. This is a shortlist from the retrieved catalogs and feeds,
not proof that no closer station exists in other networks.

| Candidate | ThaiWater station ID/code | Feed distance | Graph result |
| --- | --- | --- | --- |
| Suan Chaloem Phra Kiat Rama IX, Bang Phra seafront | 1119654/EA10 | approximately 6.24 km | 46 null rows; not usable in this fetch |
| Si Racha Fisheries Research Station | 1116457/GOT001 | approximately 8.77 km | 44 non-null hourly entries, 2 null rows |
| Chonburi | 3715/48459 | approximately 12.95 km using ThaiWater metadata | 46 null graph rows in this endpoint |

The TMD official 2024 station list uses different coordinates for Chonburi
(459201/48459), yielding approximately 11.81 km instead. Do not silently merge
the two coordinate versions. Its provincial page offers AWS 15-minute/one-hour
rainfall fields but this work did not authenticate or enable a TMD collector.

Si Racha/GOT001 is a provisional station reference because it is the closest
candidate in the fetched rain feed with known hourly values. The closer
Bang Phra station's missing graph does not prove it never operates.
A missing graph for Chonburi does not prove that all its TMD feeds are missing.

## Collected evidence

docs/P1_13_STATION_OBSERVATIONS.json stores public station metadata, relative
distance, source URL, raw response hash, exact provider timestamps, raw hourly
amounts and explicit missing-value flags for all three candidates.

Si Racha known values cover 2026-10-09 00:00 to 2026-10-10 20:00 as returned by
the provider. The latest known amount is zero. There are 44 non-null rows,
not 44 continuous guaranteed hours. No value was interpolated or inferred.
The ThaiWater renderer labels rain_24h_graph's rainfall_value series as hourly
rainfall; the endpoint name does not mean each graph row is a 24-hour sum.
The rain_24h latest endpoint separately exposes rain_1h and rain_24h.

Exact accumulation interval start/end semantics and the timezone contract still
need verification before aligning these rows with forecast hour intervals.
Provider-time strings are retained. Asia/Bangkok is a hint, not a verified UTC
conversion in the dataset. No accuracy score or missed-alert count was computed.

GOT001 is described by HII as a marine telemetry system at the Si Racha fisheries
research site. Coastal siting and distance matter when judging representativeness.
This station is not a gauge at the user's point. The data are unverified provider
values, not an independent certification of instrument performance.

References:
- https://www.thaiwater.net/
- https://chonburi.thaiwater.net/rainfall
- https://www.tmd.go.th/weather/province/chonburi
- https://www.tmd.go.th/media/ServicePages/20240909_tmd_127stations-2.pdf
- https://hydro-hims.hii.or.th/ocean/

## Point reports

docs/P1_13_POINT_OBSERVATION_TEMPLATE.json is an empty template, not an observation.
No manual observation has yet been supplied or recorded.

A report should include:
- Local date/time with +07:00 and the place actually observed.
- raining / not_raining / not_observed.
- Approximate start/end times when personally known, otherwise null.
- Whether this was a point check or continuous observation over an interval.
- Optional comments/photo reference; no invented mm estimate without a gauge.

A brief Thai report can use: date/time; place; rain state; known start/stop time.
No report means not observed. A momentary dry check cannot establish that the
whole preceding hour was dry. Subjective intensity notes remain separate from
measured millimeters. Reports from another place must not be assigned to the
system location. Do not forward a user's private point notes to public providers.

## Operational boundary

One-time collection is complete; continuous collection is not enabled.
There are no production observation inserts, scheduler changes, deployments,
LINE calls, paid integrations, commits or pushes in this follow-up.

The production observations table was empty at the earlier audit. These station
rows now exist as offline reference evidence and do not change that DB finding.
P1_13_POLICY_REPLAY.json remains a forecast-only replay, with accuracy_measured=false.

Before a collector is activated:
- Verify provider interval/timezone, missing/error codes, update delay and
  access/usage conditions. Public accessibility is not a promise of API stability.
- Keep station provenance, raw values, station scope and corrections separately
  from model-derived historical observations and manual point reports.
- Preserve missing values; dedupe by station/provider-time and metric interval.
- Confirm gauge/point correspondence before reporting forecast accuracy.
