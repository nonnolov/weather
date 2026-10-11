# Peak rainfall hour in daily alerts

Daily qualifying alerts include: ชั่วโมงที่คาดว่าฝนมากที่สุด: HH:MM–HH:MM น.

The time is selected from the same stored hourly rainfall values used for each displayed period. It is based on rainfall amount, not maximum probability. All exact tied peaks appear chronologically. Rounding is applied after choosing the peak. Preceding-hour interval semantics, local timezone and midnight endpoints are preserved.

Incomplete, invalid or conflicting rainfall coverage displays ข้อมูลไม่ครบ. If all complete hourly rainfall values are zero, the line reports ไม่มีฝนคาดการณ์ในช่วงนี้ without selecting an arbitrary hour. Below-threshold summaries retain their current format.

Qualifying template version is rain-daily-periods-v3. Frozen exact message and hourly evidence remain intact; old deliveries are not rewritten. Thresholds, dedupe, cooldown, recipients and schedule are unchanged.

Validation: 59 passed, 1 PostgreSQL-specific case skipped, 1 existing python_multipart warning. New peak-hour regressions cover amounts vs probability, ties, pre-rounding comparisons, missing/conflicting coverage, zeros and naive UTC midnight. git diff --check passed. No real LINE test is sent for this formatting change.

## Production verification

API and daily cron deployments reached SUCCESS. The current deployment formatter hash after CRLF/LF normalization matches committed source. Read-only rendering of real daily delivery 7 evidence produced peak-hour lines; the original accepted baseline was unchanged. Production proxy health returned 200. No LINE resend. See DAILY_RAIN_PEAK_HOUR_RELEASE.json.
