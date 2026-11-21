# Changelog

All notable changes. Versions follow semantic versioning; images are tagged by version.

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
