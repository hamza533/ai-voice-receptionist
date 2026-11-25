# Progress

## Status
**Milestone:** v0.2.0: Phase 1 & 2 built (schedules, time off, texts, reminders, waitlist,
value-booked card, Google Calendar connect, setup wizard). Everything that runs without the
owner's third-party keys is built, tested and green.

**Done**
- API, data model + migration, slot engine, bookings (idempotent, double-booking-safe),
  reschedule/cancel with contact verification, all 8 receptionist tools with server-side
  guardrails, auth (Argon2, sessions, CSRF, roles, rate limits), demo mode, health/ready.
- Postgres job queue + worker (embedded/separate), summaries, emails (idempotent outbox),
  retention purge, nightly demo reset.
- LiveKit Agents worker with Gemini Live (web + phone, barge-in, busy line, call time limit,
  SIP transfer option, transcript/latency/token reporting, live tool events to the web UI).
- Next.js dashboard from the Stitch design (docs/design/): landing, live call, overview, calls,
  call detail, appointments, waitlist, messages, team & schedules, knowledge, settings,
  setup wizard, login.
- Phase 1 & 2: per-person shifts and time off in the slot engine, holidays UI, Twilio texts
  (confirmations, reminders, reply C / YES) with signed webhook, waitlist with held offers,
  "value booked by Ava" + after-hours figures, Google OAuth "Connect" + calendar picker.
- Tests: 78 pytest (unit + integration on real Postgres, incl. concurrency), Playwright e2e
  (login → settings → call → call record; team hours and time off; waitlist), 30-scenario
  eval (tools mode: 100% / 0 invented slots / 0 double bookings).
- CI (lint, mypy, tsc, tests, eval, e2e, image build + Trivy, Bicep), CodeQL, Dependabot,
  disabled-by-default Azure deploy, Render blueprint, Bicep production profile.

**In progress**
- Nothing.

**Next (needs the owner's accounts/keys)**
1. Create a LiveKit Cloud project (Build plan) → set `LIVEKIT_*`; `make agent-dev`; make a web
   call from the dashboard. Claim the free US number and point its inbound rule at agent
   `luma-receptionist`.
2. Gemini API key → `GEMINI_API_KEY`; run `make eval MODE=llm` and 10 scripted voice calls;
   copy the numbers into README "Results" and the case study.
3. Google Calendar: service account + share the demo calendar → `GOOGLE_*`.
4. Gmail app password → `SMTP_*`, `STAFF_NOTIFY_EMAIL` (demo inbox).
4b. Twilio account + SMS number → `TWILIO_*`, `SMS_DEFAULT_COUNTRY_CODE`; set the number's
   incoming-message webhook to `{PUBLIC_URL}/api/sms/inbound`. Google OAuth client →
   `GOOGLE_OAUTH_CLIENT_ID/SECRET` with redirect `{PUBLIC_URL}/api/integrations/google/callback`.
5. Deploy the demo: Neon (DATABASE_URL), Render (`render.yaml`, DEMO_MODE=true), Vercel
   (`web/`, env `API_URL=https://<render-app>.onrender.com`), LiveKit Cloud agent
   (`lk agent create` with the `agent` Docker target). Set `ALLOWED_ORIGINS` to the Vercel URL.
6. Showcase video (86 s, problem-first story, warm narrator, no stack/API names) and README GIF are in
   `docs/images/` (built from the running app by `showcase/`). Optional: re-record the call
   dialogue with a female caller voice (`showcase/scripts/voiceover.py`, TTS daily quota).

## Blockers / open questions
- LLM-mode eval numbers and voice latency need `GEMINI_API_KEY` and LiveKit keys (not in repo).
- Live demo deployment needs the owner's Vercel/Render/Neon/LiveKit accounts.

## How to verify
```bash
docker compose up --build -d                      # stack on :3010 (web) and :8010 (API)
docker compose exec api python -m app.cli create-admin --email you@example.com
docker compose run --rm dev make check            # ruff, mypy, eslint, tsc, pytest → all green
docker compose run --rm dev make eval             # 30/30, 0 invented slots, 0 double bookings
cd web && E2E_BASE_URL=http://localhost:3010 npx playwright test   # 2 passed
```
Expected: `/ready` → `{"status":"ready"...}`; dashboard shows seeded Luma Hair Studio calls.

## Session log
- 2026-11-25 – Claude Code – New showcase video (86 s): problem-first story, warm narrator
  (Sulafat), female caller, text-message and waitlist scenes, faster pace and 112 BPM music;
  fresh screenshots incl. team, waitlist and setup; portfolio zip (video + screenshots).
- 2026-11-24 – Claude Code – Built Phase 1 & 2 on feat/phase-1-2: staff shifts + time off +
  holidays UI, Twilio texts and reminders with signed replies, waitlist (agent tool, offers,
  hold/expiry, dashboard), value-booked overview card, Google Calendar OAuth connect, setup
  wizard. Migration 0002. 78 tests, eval 30/30, e2e incl. new Team/Waitlist specs.
- 2026-11-24 – Claude Code – README costs: added the LiveKit Ship plan $50/month base fee and
  current LiveKit telephony rates (livekit.com/pricing, checked 2026-11-23).
- 2026-11-23 – Claude Code – Code review + security review of the MVP (security: no high/medium
  findings). Fixed 9 review findings on fix/review-findings: spoof-proof client IP for rate
  limits (TRUSTED_PROXY_HOPS), prices keep cents, reschedule/cancel keep the calendar in step
  with the database on failure, slots tied to the service they were offered for, no wrong-ref
  fallback, ambiguous service names ask instead of guess. 60 tests, eval 30/30.
- 2026-11-23 – Claude Code – Voiced showcase (single-take narrator, paced call dialogue), then
  removed all technical details from the video; plain-language call metrics in the dashboard
  (typical/slowest reply, "Actions taken", "Natural voice"). Merged PR #1 into main.
- 2026-11-23 – Claude Code – First live voice tests with LiveKit Cloud + Gemini Live: call connects,
  Ava greets (with recording notice), hears and answers, call record + AI summary saved. Fixed
  API-version 404, retired summary model, greeting notice, outcome labels, latency metric;
  switched to gemini-3.1-flash-live-preview. Added scripts/voice_test.
- 2026-11-22 – Claude Code – Built the whole MVP: API, agent, dashboard from Stitch design,
  tests, eval, CI/CD, Render + Azure Bicep, docs. Published to GitHub.
