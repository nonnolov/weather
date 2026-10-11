# P4 rainfall flood-potential screening method

## Implemented scope
A location-specific forecast-rainfall screening signal, not calibrated flood probability or confirmed inundation. API returns rainfall_flood_potential (watch), rainfall_below_trigger, or not_assessed. risk_detected is true, false, or null; false means below these rainfall triggers, not no possibility of flood.

## Numerical provenance
Reviewed 2026-10-10 UTC: DDPM OSM2Rain policy:
https://vlg-water-r.disaster.go.th/osm2rain/
It specifies observed 1-hour rainfall >=40 mm for named urban areas (Bangkok, metropolitan surrounding, Pattaya, Si Racha, Rayong, Phuket), >=75 mm for general areas; trailing observed 24h >=100 mm May-Oct or >=150 mm Nov-Apr. Rain alone supports watch, not orange/red severity.

Applying these observation criteria to forecast precipitation is OUR adaptation, not an official point-forecast flood model. No LINE alert thresholds are reused. Rule version ddpm_rain_screening_forecast_v1. The original referenced NDWC document has not been independently retrieved; provenance is the published DDPM application policy.

## Location selection
Requires matching forecast/location IDs, country TH, province metadata and finite coordinates within a broad Thailand sanity box. Bangkok aliases select 40 mm/h. General Thai locations select 75 mm/h. Other provinces containing named urban scope (metropolitan provinces, Chonburi, Rayong, Phuket) currently return not_assessed pending a verified urban boundary mapping, rather than applying one threshold to an entire province. Administrative metadata are not a verified polygon lookup; GPS geocoding and manually entered data can be wrong. This limitation is explicit in API.

## Time and missing data
Open-Meteo precipitation represents the preceding hour ending at valid_time. The horizon starts at the next wholly future hourly interval and spans 24 hours; leading gaps cannot shift the horizon forward. Conflicting duplicate timestamps, invalid/negative/nonfinite values and missing hours are not zero.
Threshold decisions use unrounded values. 1h triggers can be found in an incomplete horizon; a below-trigger result requires all 24 hours. The 24h accumulation uses a complete future 24h window; season uses Thailand local month at window end. 3h/6h totals and longest positive-rain streak are descriptive, without invented flood thresholds.
Forecast older than 6h or retrieved >5 minutes in the future cannot produce an assessment. These freshness limits are engineering policy, not DDPM observation freshness criteria.

## Historical evidence reviewed
Official Prawet district report, published 19 Aug 2022, describes flooding after heavy rain on the evening of 15 Aug 2022, district maximum accumulated rainfall 144.0 mm, high Khlong Song Hong water and delayed drainage:
https://webportal.bangkok.go.th/prawet/page/sub/10727/50/65/info/305320/เขตประเวศ-ติดตามการแก้ไขปัญหาน้ำท่วม-หมู่บ้านเดอะคอนเนค
It does not state a sufficiently precise station interval/location for paired 1h/24h replay. Excluded from scored backtesting; do not invent hourly distribution. DDS report 0004903_1.pdf could not be fetched after retries.
Historical calibration remains not_calibrated, scored events=0. Tests of rule implementation are synthetic boundary/quality tests, not accuracy validation. Need timestamped station rainfall plus independent flood and non-flood labels matched in time/space, followed by held-out evaluation of false positives/misses. Drainage, terrain, prior water, tide and river flooding remain outside this rain-only screen.

## Messaging
No LINE integration or actual sending in this step. Future existing-alert enrichment may append a flood-watch sentence only for a valid positive screening result. Below/unassessed must not append one. Public wording must preserve forecast and screening uncertainty.
