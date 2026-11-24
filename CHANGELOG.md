# Changelog

All notable changes. Versions follow semantic versioning; images are tagged by version.

## [0.2.0] – 2026-11-24
### Added
- Team page: each person's weekly working hours (or the salon's hours), time off (days,
  ranges, appointments) and weekly breaks; Ava only offers times when that person works.
- Holidays & closures card in Settings.
- Text messages through Twilio: booking confirmations, reminders (default 24 hours before)
  with "reply C to cancel", and signed replies handled by `/api/sms/inbound`.
- Waitlist: Ava offers it when a day is full (`join_waitlist` tool); a cancellation is
  offered to the first matching person, held for 30 minutes, taken by replying YES or by
  staff in the new Waitlist page, then passed to the next person.
- Overview shows the value of bookings Ava made and the calls answered while closed.
- "Connect Google Calendar" button (OAuth) with a calendar picker; the refresh token is
  stored encrypted. Service-account setups keep working.
- Setup wizard for new businesses (business, hours, team, services, calendar & texts, test
  call) with a reminder banner until it is finished.

## [0.1.0] – 2026-11-22
### Added
- FastAPI API: business config, receptionist tools, call records, dashboard API, Argon2 auth
  with sessions, CSRF and DB-backed rate limits, `/health` and `/ready`.
- Slot engine (hours, holidays, calendar busy, buffers) and double-booking-safe, idempotent
  bookings, reschedules and cancellations with Google Calendar sync.
- Server-side guardrails: no invented slots, read-back confirmation, contact-matched lookups.
- Postgres job queue (retries, backoff, dead-letter, idempotency) with embedded or separate
  worker; post-call summaries, confirmation/staff emails, retention purge, nightly demo reset.
- LiveKit Agents voice agent with Gemini Live (web + phone, barge-in, SIP transfer option).
- Next.js dashboard from the Stitch "Clinical Calm" design: landing page, live web call,
  overview, calls, call detail, appointments, messages, knowledge, settings.
- 30-scenario evaluation (tools + LLM modes), pytest suite, Playwright e2e, CI, CodeQL,
  Dependabot, image scanning, Render blueprint and Azure Bicep production profile.
