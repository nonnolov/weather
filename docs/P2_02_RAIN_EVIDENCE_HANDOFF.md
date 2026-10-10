# P2-02: measured-rain collection and point-report matching

## Scope and dependencies

The user selected the minimum P2 scope: collect actual reference data matched to forecasts, measure errors including false predictions and misses, and report counts/limitations. This step adds an offline evidence collector, validated point-report storage and an exact-scope hourly occurrence report. P2-01 remains the amount/probability evaluator for explicitly labeled archive proxy data. Model/ML changes are deferred.

Baseline review HEAD: fa80ebcfec47a472754f2005450058efa8e4dfbc. Production remains P1-14; its natural positive LINE acceptance gate is independent and open. No production observation or app files are changed.

## Implementation

- app/evaluation/rain_evidence.py: one bounded public GET for the provisionally selected GOT001/1116457 station; staged rows retain provider clocks, values, explicit gaps, raw response JSON and transport-byte hash. Each fetch is a distinct atomic JSON file, preserving subsequent corrections.
- Staging always says alignment_verified=false and evaluation_eligible=false. A plausible nonnegative amount is not instrument certification. Unknown timezones/accumulation periods are not guessed; station rainfall is not assigned to the user's point.
- Manual reports have explicit identity, immutable place scope, timezone, recording cutoff and coverage. Templates and unverified mm entries are rejected. Point checks remain evidence but cannot establish a dry hourly interval. A complete aligned hour is required by this first occurrence adapter.
- Reports match only same-scope immutable Open-Meteo rain forecasts retrieved before the entire preceding-hour period. Select the latest snapshot per hour/lead bucket. Duplicate snapshots/references cannot inflate counts; contradictory interval reports are excluded, and conflicting immutable identities fail explicitly.
- Occurrence counts: hits, misses, false alarms and correct dry; precision/recall/false-alarm ratio are null when undefined. Visual reports compare any rain, using forecast rain >0 mm, separately from P2-01's >0.1 mm total-precipitation definition. No Brier calibration or numeric amount error is inferred from visual observations.
- All manual results remain self_report_comparison with accuracy_claim_available=false. They do not verify notifier delivery, thresholds or cooldown.
- app/evaluation/rain_cli.py exposes collect-station, record-point and report. It never imports the production DB configuration or notifier. Private forecast and point files are operator inputs, not git artifacts.

## Real checks

A real station request captured 48 rows: 47 plausible values and one missing value. See P2_02_STATION_FETCHES and P2_02_COLLECTION_RESULT.json. Provider clock strings are preserved, not converted. Continuous collection is not enabled.

A bounded 90-day production forecast export ran in READ ONLY / REPEATABLE READ with a 10-second statement timeout and an explicit 10,000-row cap that fails rather than silently truncates. It found 240 elapsed hourly snapshots for the original authorized current location. Its coordinates, IDs, recipient and forecast values are kept only in a private temporary export outside git. P2_02_POINT_BASELINE.json contains the sanitized report: zero actual point references and zero selected pairs. No score is fabricated.

## Contract evidence and remaining gate

ThaiWater's official standard describes hourly accumulated rainfall as the preceding hour ending at the displayed timestamp:
https://standard.thaiwater.net/ (page: คาบเวลาของข้อมูล).
Its standard /Rainfall API describes interval-based measurements. These documents establish the standard's semantics, but do not by themselves prove that this legacy rain_24h_graph endpoint follows it, nor supply its timezone contract. The endpoint returns naive strings. Therefore the old P1-13 alignment gate is still open.

Station values are about 8.77 km away from the user's point according to the prior documented shortlist. An independent station comparison needs confirmed feed semantics and forecasts for that station's scope; it cannot establish point accuracy. Genuine manual point reports can enter the new occurrence path, with the limitations above. Numeric measured-mm error still requires an aligned gauge reference adapter/data. P2 is not complete merely because the collector runs or tests pass.

## Commands and input contract

Run from the review repo using the existing Python 3.12 installation. Paths below are placeholders, not real observations.

```powershell
python -m app.evaluation.rain_cli collect-station --directory <public-evidence-directory>
python -m app.evaluation.rain_cli record-point --input <private-actual-report.json> --directory <private-evidence-directory>
python -m app.evaluation.rain_cli report --forecasts <private-forecast-array.json> --references <private-point-array.json> --scope-id <exact-place-scope> --since <aware-timestamp> --as-of <aware-timestamp> --output <report.json>
```

Forecast array fields: scope_id, provider=open_meteo, integer run_id/row_id, aware valid_time/retrieved_at, rain_mm (unknown stays null). Reference array uses P2_02_POINT_REPORT_TEMPLATE.json; the empty template must not be recorded as a real report. Manual recording time is caller-supplied and must not be backdated; independent provenance cannot be certified by this offline adapter.

## Acceptance and verification

Tests cover parser contract drift, missing/invalid amounts, timezone equivalence, coverage/cutoff/scope gates, all four occurrence outcomes, undefined ratios, deterministic snapshot selection, conflicting identities, bucket counts, atomic/idempotent recording and CLI file-to-report flow. Targeted result: 50 passed, one existing python_multipart warning. A same-clock filename collision discovered during testing was fixed by giving each station fetch a UUID; the repeated-fetch test now passes.

Full regression and preservation results are recorded below after completion. No commit, push, deployment, LINE call or production DB write is part of this step.


The actual point export's 240 candidate rows include 187 retrieved after the accumulated period started; these are excluded from forward-looking evaluation. The remaining 53 candidates lack eligible point references. Neither number is a count of unique independent observed hours, and neither is an accuracy score.


## Completed verification

Full private credential-isolated regression: 587 passed, 18 external integration cases deselected, one existing python_multipart warning; pytest 306.31 seconds, process exit 0. New coverage adds 50 cases to the P2-01 baseline of 537. Real station requests and production read-only export are separate evidence, not mock-test accuracy validation.

Git diff --check, Python syntax and JSON validation passed. Review HEAD/branch and empty index are preserved. The 21 tracked P1 notification files have no git content changes (normal Windows checkout newline differences are accounted for). All 34 protected dirty files in the original worktree retain their original checkpoint hashes, HEAD/branch and empty index. The P2 review contains 22 pending files including the existing P2-01 package; nothing is committed, pushed or deployed.

P2-02 software and its offline end-to-end checks are complete. The minimum P2 data acceptance remains open: verify the station endpoint contract and obtain aligned measured references or genuine point reports. A report with zero eligible pairs is the correct current result, not evidence of perfect or zero accuracy. No LINE call or production DB write occurred.
