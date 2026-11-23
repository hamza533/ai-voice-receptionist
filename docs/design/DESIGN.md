# Design – Receptly dashboard (from the Stitch project)

Source: Stitch project "AI Voice Receptionist Web App" (id 12976362211695147093), design system **"Clinical Calm"**.
The Stitch screens were drawn as 390 px mobile screens for a dental demo ("Bright Smile Dental").
This app keeps that design system, component style and screen set, and adapts them to:

- a **responsive desktop-first web app** (1440 px baseline, collapses to the mobile layouts below 768 px), and
- the spec's demo business, **Luma Hair Studio** (24 Market Street, Asia/Karachi, PKR prices;
  staff Sara – stylist, Omar – barber), with the receptionist persona **Ava**.

## Tokens (exact values from Stitch)

| Token | Value | Use |
|---|---|---|
| primary | `#00685b` | buttons, active nav, links |
| primary-container | `#008373` | gradient end on primary buttons |
| brand teal | `#0f9d8a` | logo mark, focus ring, accents |
| primary-fixed | `#83f6e0` | "AI Active" and success pills |
| mint accent | `#e8f7f4` | agent chat bubbles, selected rows |
| on-surface (deep navy) | `#0b1c30` | headings and body text |
| on-surface-variant | `#3d4946` | secondary text |
| surface / background | `#f8f9ff` | page canvas |
| surface-container-low | `#eff4ff` | caller chat bubbles, inputs |
| surface-container | `#e5eeff` | chips, segmented controls |
| surface-container-lowest | `#ffffff` | cards |
| outline-variant | `#bcc9c5` | hairlines |
| secondary | `#505f7a` | neutral badges |
| error | `#ba1a1a` | end call, cancelled |
| warning amber | `#f59e0b` | unanswered questions, callbacks |
| success green | `#10b981` | confirmed, connected |

Typography: **Inter** everywhere. Scale: display 48/56 700, headline-lg 32/40 700, headline-md 24/32 600,
headline-sm 20/28 600, title-md 16/24 600, body-lg 16/24, body-md 14/20, label-md 13/18 500,
label-sm 11/16 600 uppercase tracking 0.03em, caption 12/16. Negative letter-spacing on headings ≥ 20 px.

Radius: sm 4px, default 8px, md 12px, lg 16px, xl 24px, pills full. Cards use 16px radius.
Elevation: L1 card = white + 1px `#e2e8f0` border + `0 1px 3px rgba(11,27,51,.04)`; L2 hover = `0 4px 6px -1px rgba(11,27,51,.06)`.
Icons: Material Symbols Outlined (dashboard uses lucide equivalents via shadcn).
Spacing: 8pt rhythm; desktop margins 32px, gutters 24px; card padding 16/24px.

## Signature components

- **Header**: brand mark (rounded teal square), business name in label-sm uppercase teal, "● AI Active" mint pill, page title, notification bell with red dot, avatar.
- **Primary button**: teal gradient (`#00685b` → `#008373`), white text, 12px radius, subtle shadow. Secondary: white card button.
- **Stat tile**: white card, small icon chip top-left, trend pill top-right (`+18%`), large number (32px 700), caption. One highlighted tile is solid primary with white text ("Appointments booked").
- **Status pills**: Appointment Booked (mint), FAQ Answered, Rescheduled, Cancelled (red dot), Transferred, Message; sentiment pill (Positive / Neutral).
- **AI summary block**: mint panel with sparkle icon and one-line summary; key date bold teal.
- **Transcript**: caller bubbles right-aligned on `#eff4ff`; agent bubbles left on mint with "✦ AI Agent" tag and timestamp; **tool-call chips** inline ("🔍 00:18 Checked availability in Google Calendar", "📅 00:52 Booked: Tue Nov 25, 2:30 PM").
- **Live call**: concentric pulsing teal orb with waveform glyph, "Connected — Listening… 04:12" pill, Mute / Keypad / End call (red) round buttons, demo-mode notice ("Calls limited to 3 mins"), "What the AI is doing" step list (checked availability → offered times → booked appointment → sent confirmation).
- **Charts**: weekly call bars (teal, peak day darker with label), resolution donut (Booked / FAQ / Rescheduled / Cancelled-Transferred) with legend percentages.
- **Schedule**: date strip, day timeline with appointment blocks per staff, selected block solid primary, "AI Booked" tag.
- **Knowledge**: FAQ cards with "Ava's trained response", usage count and toggle; amber "Unanswered questions this week" alert; "Test Ava's knowledge" chat.
- **Settings**: grouped cards — Greeting & Persona (greeting textarea, voice list with Listen buttons), Hours & After-Hours (day toggles), Booking durations & buffers, Human escalation & handoff, Integrations (Google Calendar, email, phone number), sticky "Save changes".

## Screens → routes

| Stitch screen | Route | Notes |
|---|---|---|
| 1 Landing page | `/` | Hero "Never miss a call again", Talk to the receptionist CTA, live call preview, stats, How it works, features, CTA |
| 3 Dashboard overview | `/dashboard` | KPIs, weekly calls, resolution donut, upcoming today, recent calls |
| 4 Calls list | `/dashboard/calls` | date range, search, outcome filter chips with counts, call cards |
| 5 Call detail | `/dashboard/calls/[id]` | caller card, transcript with tool chips, AI summary, appointment, latency |
| 2 Live demo call | `/call` and dashboard "Talk to receptionist" | WebRTC via LiveKit, live transcript, "What the AI is doing" |
| 6 Appointments | `/dashboard/appointments` | week strip + day timeline + details panel |
| 7 Knowledge | `/dashboard/knowledge` | FAQs CRUD with toggles, test panel |
| 8 Agent settings | `/dashboard/settings` | business, services, staff, hours, voice, greeting, handoff, email |
| (new) Messages | `/dashboard/messages` | callbacks, urgent flag, mark handled |
| (new) Login | `/login` | same card style |

Improvements over the mock: Audio recording card is shown only when recording is enabled (spec stores no audio by default); "SMS sent" becomes "Email sent" (SMS is out of scope); numbers on screens come from the API, not hard-coded.
