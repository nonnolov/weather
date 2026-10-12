# Current master roadmap (P0-P7)

Current status 2026-10-12 Asia/Bangkok: Map and the consent-based LINE signup Dashboard are live. Daily/intraday sending is temporarily paused pending explicit enrollment and real-user verification; the earlier sending/allowlist descriptions below are historical. See LINE_ONBOARDING_PRODUCTION_RELEASE.json and LINE_ONBOARDING_HANDOFF.md.

Source: user Master prompt in the "ใช้ Remote Desktop" conversation, 2026-10-09. This numbering supersedes the repository's initial six implementation milestones.

| Phase | User-defined scope |
| --- | --- |
| P0 | Production Baseline & Reliability |
| P1 | Intraday Weather Forecast & Alerts |
| P2 | Forecast Accuracy Evaluation & Improvement |
| P3 | PM2.5 |
| P4 | Rainfall-Based Flood Risk |
| P5 | Real Flood Data (optional by access) |
| P6 | Unified Dashboard |
| P7 | End-to-End Verification & Production Freeze |

Every phase must state Dependencies, Risks, Scope, Tests and verifiable Acceptance Criteria. A change of order requires evidence and an explained rationale. Review the current task before starting another.

## Current work status

P1 code, mocked/local validation, deployment and GitHub publishing are complete for the revised intraday policy. Positive naturally qualifying intraday LINE API acceptance plus committed evidence, and handset receipt, remain open verification items. P1 is not marked fully verified.

On 2026-10-10 the user requested starting P2 without waiting for a natural P1 event. P2 data/evaluation work can proceed independently while P1 stays active. No artificial P1 event is created to close its gate.

P2-01 is the current implementation task: audit forecast/reference pairing, provenance and time semantics; report explicit empty/ineligible results; fix populated legacy metric serialization and a negative subsecond lead check; use a separate documented archive request contract. See P2_01_EVALUATION_HANDOFF.md.

## P2 completion criteria and remaining work

- Obtain reference data that can be matched to immutable forecast snapshots at the same location and interval; identify reanalysis separately from measured station or point data.
- Report amount errors, occurrence errors and probability calibration by forecast horizon with sample counts and reference provenance.
- Establish a numerical baseline from eligible real data; empty data is not a zero-error score.
- Correction or ML improvement is deferred from the user's selected minimum scope. Before any later correction activation, review time/target leakage and reference availability and show improvement on later held-out data.
- Validate the complete data-to-report path and document limitations. P2 is not complete merely because code tests pass.

The next implementation step is reference acquisition/pairing for elapsed forecast periods, including previously forecasted locations rather than only today's current location. Nearby station and at-point observations require verified interval/provenance and quality checks before they become independent validation evidence. These implementation steps refine P2; they are not extra master phases.


P2-02 follow-up: offline GOT001 collection, explicit manual point-report recording and hourly same-scope occurrence matching are implemented. See P2_02_RAIN_EVIDENCE_HANDOFF.md. Actual station rows are staged, with their endpoint timezone/interval verification gate still open. Current-point reports are absent; numerical baseline acceptance is still pending. No automatic collector or P2 production rollout is enabled.


P2-03 release adds an hourly API-process collector and durable, separate station-fetch history plus GET /api/v1/rain-reference/status. Data stay quarantined while the legacy endpoint contract is unconfirmed. Local verification passes 605 cases. See P2_03_AUTOMATIC_COLLECTION_HANDOFF.md for deployment verification; the minimum P2 numerical baseline gate remains open.


P3-01: separate PM2.5/model air-quality API and bilingual dashboard card implemented. Source Open-Meteo/CAMS Global; European AQI explicitly labeled, epoch/GMT times, missing/stale handling and a bounded cache. See docs/P3_01_AIR_QUALITY_HANDOFF.md (P3_01_AIR_QUALITY_HANDOFF.md from docs). P2 remains active in quarantine with its reference-alignment and numerical-baseline gates open. P1 natural positive acceptance/handset verification remains open. Production release verified; see docs/P3_01_PRODUCTION_RELEASE.json.


P4-01: forecast rainfall exposure report/API and bilingual dashboard card implemented on the review branch. It reports rolling 1/3/6/24-hour forecast accumulations and coverage but deliberately leaves flood risk unassessed. P4-02 now follows the user's clarified scope: estimate rainfall-driven flood potential at a user's location from local forecast rain amount and duration, with area-specific thresholds derived and validated from historical rain/flood evidence; LINE alert thresholds are excluded. P4-03 source feasibility found HII hourly rain history, GISTDA flood evidence and Bangkok flood-risk/monitoring datasets, but a validation-ready joined dataset and location coverage are not confirmed. See docs/P4_01_RAINFALL_EXPOSURE_HANDOFF.md, docs/P4_02_RISK_ASSESSMENT_METHOD.md and docs/P4_03_EVIDENCE_FEASIBILITY.md. Risk remains not_assessed; not deployed or committed.

P4 update 2026-10-10 UTC: steps 1-2 now have DDPM-source rainfall screening and a tested per-location evaluator/UI (35 focused tests). Historical calibration remains not_calibrated (0 scored events); P4 not complete. See P4_04_SCREENING_IMPLEMENTATION_HANDOFF.md and current P4_02_RISK_ASSESSMENT_METHOD.md. LINE enrichment not yet implemented/enabled.

P4 update 2026-10-11 Asia/Bangkok: existing daily/intraday Alert text enrichment implemented; a flood-watch note appears only for a valid positive screen. Related 91-case suite passed including isolated PostgreSQL locking/delivery tests with mock LINE. See P4_05_LINE_ENRICHMENT_HANDOFF.md. Historical calibration remains incomplete; production release is not part of the dry-run validation.

P1 update 2026-10-11 17:06 Asia/Bangkok: user-authorized real daily delivery succeeded for current location 15 (delivery 7, source 69). LINE accepted HTTP 200, exact text/24-hour evidence committed, duplicate daily attempt suppressed, production dry-run intraday preview suppressed identical_content with a readable baseline. The morning delivery belonged to another location record; it remains intact. Handset receipt and a naturally qualifying intraday accepted-send/replay gate remain open. See P1_DAILY_BASELINE_VERIFICATION.md/json.

## User-selected daily-use scope — 2026-10-11 19:28 Bangkok

The user retained Open-Meteo and prioritized an everyday usable release over completing forecast-accuracy research. See DAILY_USE_RELEASE.md and DAILY_USE_ACCEPTANCE.json for current production checks, the minimum P6/P7 disposition and the original gates explicitly deferred. P2 numerical validation and optional P5 real flood data are not blocking this controlled release. This does not mark all original phases fully verified, expand recipients or claim a calibrated local flood forecast. The existing deployed runtime is retained; the closure adds only a GET-based operator smoke check and release records.

## User scope change — 2026-10-11 21:18 Bangkok

The user removed the accumulated-rain/flood-risk dashboard card and flood-watch text from both daily and intraday LINE alerts. P4 is withdrawn from the everyday product scope, rather than declared fully validated. Standard rain forecast amounts and alert rules remain. See REMOVE_FLOOD_UI_LINE_HANDOFF.md and REMOVE_FLOOD_UI_LINE_RELEASE.json for implementation and production evidence; historical P4 records are retained.
