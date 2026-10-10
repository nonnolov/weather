# Current master roadmap (P0-P7)

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


P3-01: separate PM2.5/model air-quality API and bilingual dashboard card implemented. Source Open-Meteo/CAMS Global; European AQI explicitly labeled, epoch/GMT times, missing/stale handling and a bounded cache. See docs/P3_01_AIR_QUALITY_HANDOFF.md (P3_01_AIR_QUALITY_HANDOFF.md from docs). P2 remains active in quarantine with its reference-alignment and numerical-baseline gates open. P1 natural positive acceptance/handset verification remains open. Release outcome is recorded after verification.
