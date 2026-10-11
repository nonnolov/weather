# Real daily baseline verification

On 2026-10-11 the user authorized checking/sending the real daily alert today instead of waiting for tomorrow.

## Verified result

At 17:06 Asia/Bangkok, the deployed production function send_rain_alert sent one real forecast daily message to the established sole recipient. LINE accepted HTTP 200, request ID 72090a68-0f40-4a45-886e-7654793ad593. The successful transaction committed delivery 7 for current location 15 and actual persisted forecast run 69. Frozen evidence contains the exact accepted message and 24 hourly intervals. No example weather or synthetic intraday event was inserted.

A read-only preflight found the morning daily delivery 6 belongs to location record 13, while the user's current location record is 15. This explains no_baseline for the current scope. Location display names can refer to a similar area without making their stored location IDs interchangeable. Existing delivery 6 and its source/history were not rewritten or reused for a different location.

The production formatter, daily sender and LINE client matched deployed commit 6081939 after normalizing CRLF/LF; raw physical hashes differ due to line endings. An initial strict physical-hash guard stopped before any LINE push. Read-back confirmed no current-location delivery, and normalized code verification passed before the one successful push.

## Path and checks

Execution ran inside the current API container through authorized SSH and the deployed daily sender, with the existing recipient scope/daily dedupe locks and real LINE client. The cron itself was not triggered; no all-user batch, observation ingestion, extra refresh, deployment, variable change or schedule change was performed.

The current user assignment was locked and checked against the preflight location. The latest stored forecast was checked for age no greater than 90 minutes. The successful sender's response and exact text were captured for read-back; no network retry was performed. Existing records were preserved.

After commit, read_latest_rain_baseline returned a known baseline for the current location. A second daily invocation with a must-not-send client returned false, validating dedupe without another LINE request. The production intraday preview (dry_run=True, no client) read the committed snapshot and returned suppress/identical_content. The current scope no longer returned no_baseline. This preview does not prove that an actual significant intraday change has been sent.

## Remaining acceptance

Handset receipt awaits user confirmation. P1 remains open until a naturally qualifying intraday change receives LINE API acceptance with committed exact evidence and post-send replay/cooldown verification. A successful manual daily check is not automatic-cron execution evidence or proof of an intraday weather event.

Machine-readable evidence: docs/P1_DAILY_BASELINE_VERIFICATION.json.
