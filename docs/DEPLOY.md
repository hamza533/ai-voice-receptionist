# Go live: public demo checklist

The demo runs on free tiers: dashboard on **Vercel**, API on **Render** (`render.yaml`),
database on **Neon**, voice agent and phone number on **LiveKit Cloud**. Texts (Twilio),
email (SMTP) and "Connect Google Calendar" are optional and can be added at any time.

Allow about 45 minutes. Keep every secret in the provider's settings: never in git or chat.

## 0. Before you start

| You need | Free tier | Used for |
|---|---|---|
| GitHub repo access | yes | Render and Vercel deploy from it |
| [Neon](https://neon.tech) account | yes | Postgres database |
| [Render](https://render.com) account | yes | API + job worker (sleeps when idle) |
| [Vercel](https://vercel.com) account | yes | Dashboard, landing page, web calls |
| [LiveKit Cloud](https://cloud.livekit.io) project | yes (Build plan) | Calls, agent hosting, phone number |
| Gemini API key ([AI Studio](https://aistudio.google.com/apikey)) | yes | Ava's voice, call summaries |
| Optional: [Twilio](https://console.twilio.com) | trial | Confirmation and reminder texts |
| Optional: [Google Cloud](https://console.cloud.google.com) OAuth client | yes | "Connect Google Calendar" |
| Optional: Gmail app password | yes | Confirmation and staff emails |

Generate one long random value for `AGENT_SERVICE_TOKEN` (Render generates `SESSION_SECRET`):

```powershell
$b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })
```

## 1. Database (Neon)

1. New project, region closest to your users.
2. Copy the connection string and change the scheme to `postgresql+psycopg://`, keeping
   `?sslmode=require`. This is `DATABASE_URL`.

## 2. API (Render)

1. **New → Blueprint**, pick this repository. Render reads `render.yaml`.
2. Fill the values marked `sync: false`:
   - `DATABASE_URL` (step 1), `AGENT_SERVICE_TOKEN` (step 0)
   - `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (LiveKit → Settings → Keys)
   - `GEMINI_API_KEY`
   - `ALLOWED_ORIGINS` and `PUBLIC_URL`: leave empty for now, filled in step 4
   - optional ones (Twilio, Google OAuth, SMTP): leave empty
3. Deploy. Migrations run on start. Check `https://<render-app>.onrender.com/ready` shows
   `"status": "ready"`.

## 3. Demo data and your admin login

Run once from your machine, against the Neon database (Docker only, nothing to install):

```powershell
$env:DATABASE_URL = "<the Neon URL from step 1>"
docker compose run --rm -e DATABASE_URL init python -m app.seed --demo --reset
docker compose run --rm -e DATABASE_URL init python -m app.cli create-admin --email you@yourdomain.com
```

The second command asks for the password; it is never shown or stored in plain text.

## 4. Dashboard (Vercel)

1. **Add New → Project**, import this repository, **Root Directory: `web`**.
2. Environment variable: `API_URL = https://<render-app>.onrender.com`. Deploy.
3. Back in Render, set `ALLOWED_ORIGINS` and `PUBLIC_URL` to the Vercel URL
   (e.g. `https://receptly-demo.vercel.app`) and redeploy.
4. Open the Vercel URL, sign in with the admin from step 3.

## 5. Voice agent (LiveKit Cloud)

Deploy the `agent` target of the `Dockerfile` with LiveKit Cloud agent hosting (see LiveKit's
"Deploy to LiveKit Cloud" guide; the `lk` CLI builds and uploads it). Agent settings:

| Variable | Value |
|---|---|
| `API_URL` | `https://<render-app>.onrender.com` |
| `AGENT_SERVICE_TOKEN` | same value as on Render |
| `GOOGLE_API_KEY` | your Gemini API key |
| `LIVEKIT_AGENT_NAME` | `luma-receptionist` |

LiveKit provides `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` to hosted agents.
Test: on the Vercel site, **Talk to the receptionist**. The first call after idle can take a few
seconds (free plans sleep).

## 6. Phone number (LiveKit Cloud)

**Telephony → Phone numbers**: claim the free US number, then add an inbound **dispatch rule**
that sends calls to agent `luma-receptionist`. Call it and book something.

## 7. Optional add-ons

- **Texts (Twilio):** buy an SMS-capable number; set `TWILIO_ACCOUNT_SID`,
  `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` (and `SMS_DEFAULT_COUNTRY_CODE`, e.g. `+92`) on
  Render. In the number's settings, set **A message comes in** to
  `https://<vercel-url>/api/sms/inbound` (HTTP POST). Trial accounts only text verified numbers.
- **Connect Google Calendar:** Google Cloud → enable the Calendar API → OAuth consent screen →
  Credentials → OAuth client ID (Web) with redirect URI
  `https://<vercel-url>/api/integrations/google/callback`. Set `GOOGLE_OAUTH_CLIENT_ID` and
  `GOOGLE_OAUTH_CLIENT_SECRET` on Render, then Settings → Integrations → **Connect**.
- **Email:** Gmail → App passwords; set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`,
  `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` and `STAFF_NOTIFY_EMAIL` on Render.

## 8. Final check

- `/ready` on the API is `ready`; Settings → Integrations shows what is connected.
- A web call and a phone call each create a call record with a summary.
- With texts on: book with your mobile, receive the confirmation, reply **C**, receive the
  cancellation.
- Demo mode resets bookings nightly; keep `DEMO_MODE=true` for the public demo only.
