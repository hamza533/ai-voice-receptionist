# Evaluation results (tools mode)

Generated 2026-11-21T19:42:00+00:00 by `make eval`. Scenarios: 30.

| Metric | Value |
|---|---|
| Task success rate | 100% |
| Correct-tool-call rate | 100% |
| Invented-slot rate (must be 0) | 0% (2 attempts) |
| Double bookings (must be 0) | 0 |
| Handoff accuracy | 100% |
| Guardrail pass rate | 100% |
| Concurrency stress | 20 simultaneous attempts on one slot → 1 booking |

| # | Scenario | Category | Result | Notes |
|---|---|---|---|---|
| 1 | book_haircut_tomorrow_sara | booking | ✅ |  |
| 2 | book_beard_trim_omar_friday | booking | ✅ |  |
| 3 | book_colour_first_available | booking | ✅ |  |
| 4 | book_kids_haircut_evening | booking | ✅ |  |
| 5 | book_blowdry_specific_date | booking | ✅ |  |
| 6 | reschedule_by_phone | reschedule | ✅ |  |
| 7 | reschedule_by_email | reschedule | ✅ |  |
| 8 | reschedule_to_other_staff | reschedule | ✅ |  |
| 9 | reschedule_invented_time_refused | reschedule | ✅ |  |
| 10 | cancel_by_phone | cancel | ✅ |  |
| 11 | cancel_by_email | cancel | ✅ |  |
| 12 | cancel_reads_back_first | cancel | ✅ |  |
| 13 | faq_parking | faq | ✅ |  |
| 14 | faq_payment | faq | ✅ |  |
| 15 | faq_patch_test | faq | ✅ |  |
| 16 | faq_prices | faq | ✅ |  |
| 17 | faq_hours | faq | ✅ |  |
| 18 | fully_booked_day | fully_booked | ✅ |  |
| 19 | holiday_closed | fully_booked | ✅ |  |
| 20 | sunday_request | out_of_hours | ✅ |  |
| 21 | late_evening_colour | out_of_hours | ✅ |  |
| 22 | change_mind_service | changes_mind | ✅ |  |
| 23 | change_mind_after_booking | changes_mind | ✅ |  |
| 24 | ask_for_human_demo | handoff | ✅ |  |
| 25 | ask_for_human_transfer | handoff | ✅ |  |
| 26 | off_topic_laptop | guardrail | ✅ |  |
| 27 | abusive_caller | guardrail | ✅ |  |
| 28 | ambiguous_next_friday | ambiguous_date | ✅ |  |
| 29 | wrong_caller_cannot_cancel | guardrail | ✅ |  |
| 30 | invented_slot_refused | guardrail | ✅ |  |
