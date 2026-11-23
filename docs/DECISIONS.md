# Decisions

Short entries: chose X over Y because Z. This is the "Stack" part of the case study.

## Stack (from SPEC)
- **LiveKit Agents over Vapi/Retell**: open source and self-hostable, WebRTC and SIP in one
  framework, built-in barge-in and turn detection, free Build plan. No platform lock-in.
- **Gemini Live native audio over an STT → LLM → TTS pipeline**: one model, lower delay, natural
  voice, function calling, $0 in development. LiveKit lets us swap to a pipeline later.
- **FastAPI + Pydantic v2**: typed validation and OpenAPI docs the client can try.
- **PostgreSQL job queue over Redis/Celery**: one database to run; `SKIP LOCKED` gives safe
  concurrency; jobs are inserted in the same transaction as the data (transactional outbox).
- **Google Calendar via a service account**: free and what small businesses use.
- **SMTP over SMS**: free and provider-neutral; SMS is a paid add-on.
- **Next.js + shadcn/ui + Tailwind**: same front-end stack as the other projects; components are
  copied into the repo (shadcn's current Base UI variant).

## Made during the build
- **API owns the instructions (prompt)**: `calls/start` returns instructions built from the
  business config, so settings changes apply on the next call without redeploying the agent.
- **"Never invent a slot" enforced server-side**, not only in the prompt: book/reschedule accept
  only `slot_id`s returned by `check_availability` in the same call. A prompt can be ignored by
  a model; a database check cannot.
- **Read-back enforced with `caller_confirmed`** on booking and a dry-run response on
  reschedule/cancel.
- **Deterministic outcome labels from tool results, LLM only for the summary text**: the outcome
  (booked, cancelled…) is a fact in our own records; using the LLM for it would add errors.
- **Calendar `events.list` instead of `freebusy`**: freebusy can't tell which stylist an event
  blocks on a shared calendar; events carry `staff_id` in private extended properties and
  receptionist events are de-duplicated against the database by event id.
- **Unique index covers `booked` and `rescheduled`** (spec said `booked`): a rescheduled
  appointment is still an active booking and must block its slot.
- **Keyword FAQ matching over embeddings**: ~10–50 FAQs per business; overlap + light stemming is
  predictable, free and needs no vector store (spec: no RAG). Misses are listed in the dashboard
  as "Unanswered questions this week".
- **Dashboard calls the API through Next.js rewrites** (`/api/*`): session cookies are
  first-party on Vercel + Render without third-party cookies, and CORS stays strict.
- **DB-backed rate limits** instead of in-memory: correct with several API replicas.
- **"Next friday" returns both candidate dates** when ambiguous, and the agent asks; silently
  picking one is how wrong bookings happen.
- **Spread-out slot offers** (max 3 per day, ≥ 60 min apart): callers get useful choices.
- **`cn` package (shadcn-ui/cn)**: installed by shadcn's current init; replaces clsx +
  tailwind-merge. Accepted because it comes from the shadcn org and is MIT.
- **Docker "dev" toolbox target**: `docker compose run --rm dev make check` works on machines
  without uv/Node (the build machine is Windows without either).
- **Evaluation in two modes**: deterministic tools mode (CI, no key, enforces 0 invented slots /
  0 double bookings) and LLM mode (Gemini caller + judge) for conversation quality.

## New dependencies (beyond the spec list)
- `sentry-sdk` – optional error tracking (CONVENTIONS §10), off unless `SENTRY_DSN` is set.
- `email-validator` – Pydantic `EmailStr` for login.
- `livekit-api` – minting room-limited tokens in the API (agent dispatch in the token).
- `@livekit/components-react`, `livekit-client` – web calls in the dashboard (spec).
- `@playwright/test` – end-to-end tests (CONVENTIONS).

## Found in live voice testing (2026-11-23)
- **Voice model `gemini-3.1-flash-live-preview` over `gemini-2.5-flash-native-audio`**: measured
  0.5–0.7 s to first audio vs 1.2–1.3 s, and correct tool-argument names (the 2.5 model sent
  `date` instead of `date_from`). Still configurable with `VOICE_MODEL`.
- **Pin the Gemini API to `v1beta`** (`GEMINI_API_VERSION`): the SDK default returns HTTP 404 on
  the Live WebSocket for current keys.
- **Recording notice inside the greeting, before the closing question**: the voice model dropped
  a notice appended after "How can I help?". It is now mid-greeting and repeated as rule 0 of
  the instructions.
- **LLM fallback chain** (`LLM_FALLBACK_MODELS`): `gemini-2.5-flash` is retired for new keys and
  the newest Flash models often return 503 on the free tier; summaries try the next model, 4xx
  errors are not retried, and a call always gets at least a rule-based summary.
- **Outcome for calls with no tool action comes from the summary model** (FAQ answered vs
  abandoned) instead of guessing from the number of caller turns.
- **Accept ISO datetimes as dates** ("2026-11-24T12:00:00"), which the live model sometimes sends.
