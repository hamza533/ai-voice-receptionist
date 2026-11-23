# AGENTS.md

## Project
Never miss a call: an AI receptionist that answers, books appointments in your calendar and
hands off to a human when needed. Full requirements: docs/SPEC.md. Shared rules:
docs/CONVENTIONS.md. UI design: docs/design/DESIGN.md (from the Stitch project).

## Start here
1. Read docs/PROGRESS.md (current status + next step).
2. Read docs/SPEC.md and docs/DECISIONS.md before changing the stack.

## Commands
make setup | make dev | make test | make lint | make check | make eval | make seed
Also: make db (Postgres only, for tests), make create-admin EMAIL=…, make agent-dev, make e2e.
No uv/Node on your machine (e.g. Windows)? `docker compose run --rm dev make check`.

## Structure
```
app/            FastAPI API: models, tools, booking, jobs, auth (all business logic)
  api/          routers: public, dashboard, settings, agent (service token)
  services/     availability, booking, calendar, email, tools, prompt, privacy, timeutil
  jobs/         Postgres job queue, worker, handlers (summaries, emails, purge, demo reset)
agent/          LiveKit Agents worker (thin: relays audio, calls API tools)
web/            Next.js 16 + shadcn/ui dashboard, landing page and web-call page
migrations/     Alembic
tests/          pytest unit + integration (real Postgres)
eval/           30 scenarios, runner, committed results
sample_data/    synthetic demo business (Luma Hair Studio)
deploy/azure/   Bicep production profile (validated in CI, not deployed)
docs/           SPEC, CONVENTIONS, PROGRESS, DECISIONS, architecture, design
```

## Rules
- Follow docs/SPEC.md stack; adding a dependency requires a DECISIONS.md entry.
- `make check` must pass before committing; never commit secrets.
- Small conventional commits on a feat/ or fix/ branch.
- End every session by updating docs/PROGRESS.md (status, next step, session log line).
- Business rules live in the API (`app/services/tools.py`, `booking.py`), never in the agent.
- UI follows docs/design/DESIGN.md tokens (Clinical Calm); use shadcn/ui components.

## MCP servers
| Server | Why | Claude Code | Cursor / Codex / Antigravity |
|---|---|---|---|
| shadcn | install/browse UI components | in .mcp.json | `pnpm dlx shadcn@latest mcp init --client cursor` (or `codex`); Antigravity: add `npx shadcn@latest mcp` in its MCP settings |
| neon (deploy step only) | manage the demo DB | `claude mcp add --transport http neon https://mcp.neon.tech/mcp` then `/mcp` to log in | add URL `https://mcp.neon.tech/mcp` in the tool's MCP settings |

## Gotchas
- **Gemini Live free tier:** few concurrent sessions and occasional 1011/overload errors.
  The agent says a busy line and hangs up; the dashboard shows "Receptionist is busy, try
  again in a minute". Free-tier data may be used by Google: synthetic data only.
- **LiveKit Build plan:** max 5 concurrent agent sessions, 1,000 agent minutes/month, agents
  cold-start after idle (first call can take a few seconds to be answered).
- **Time zones:** everything is stored in UTC; speech and the dashboard use the business time
  zone (`business_config.timezone`). Never build datetimes without a tzinfo.
- **Never invent slots:** `book_appointment`/`reschedule_appointment` only accept a `slot_id`
  returned by `check_availability` in the same call. Keep that check server-side.
- **Calendar sharing:** share the business Google Calendar with the service account email
  ("Make changes to events") or every call fails with 404/403. Without credentials the
  built-in local calendar is used.
- **Demo calendar reset:** with `DEMO_MODE=true` a nightly job deletes bookings (and their
  calendar events) and reseeds sample data. Don't point demo mode at a real calendar.
- **Thin agent:** the agent only relays audio and calls API tools; changing a rule in the
  agent instead of the API breaks the eval and the guarantees above.
- **Next.js 16:** `middleware` is now `proxy`, request APIs are async, Turbopack is default.
  The dashboard calls the API through `/api/*` rewrites (first-party cookies).
- **Windows + Docker bind mounts:** npm/Next rename files during install/build; build web in
  the container filesystem (see Makefile/CI) rather than on a bind mount.
