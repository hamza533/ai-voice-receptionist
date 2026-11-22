import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

import { Backdrop, BrandMark, BrowserFrame, Callout, Pill, PhoneFrame, Title, ease, useEnter, useSpring } from "./components";
import { C, fontFamily } from "./theme";

/** Maps a point in the 2000-px-wide screenshot preview space to the video frame. */
function mapper(left: number, top: number, width: number, cropTopView = 0) {
  const f = width / 2000;
  return (x: number, y: number, w: number, h: number) => ({
    x: left + x * f,
    y: top + 44 + (y - cropTopView) * f,
    w: w * f,
    h: h * f,
  });
}

function useCamera(from: number, to: number, frames: number) {
  const frame = useCurrentFrame();
  return interpolate(frame, [0, frames], [from, to], { extrapolateRight: "clamp", easing: ease });
}

// ---------------------------------------------------------------- 1. intro

export function IntroScene() {
  const frame = useCurrentFrame();
  const s = useSpring(4, 14);
  const word = useEnter(16, 26);
  const tag = useEnter(30, 26);
  const pill = useEnter(46, 22);
  return (
    <AbsoluteFill style={{ fontFamily, alignItems: "center", justifyContent: "center" }}>
      <Backdrop dark />
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 28 }}>
        <div style={{ transform: `scale(${0.4 + 0.6 * s}) rotate(${(1 - s) * -20}deg)`, opacity: Math.min(1, s * 2) }}>
          <BrandMark size={140} />
        </div>
        <div style={{ opacity: word, transform: `translateY(${(1 - word) * 24}px)`, fontSize: 104, fontWeight: 800, color: "white", letterSpacing: "-0.04em" }}>
          Receptly
        </div>
        <div style={{ opacity: tag, transform: `translateY(${(1 - tag) * 18}px)`, fontSize: 38, color: "rgba(255,255,255,0.8)", fontWeight: 500 }}>
          The AI receptionist that never misses a call
        </div>
        <div style={{ opacity: pill, marginTop: 8 }}>
          <Pill style={{ fontSize: 22, padding: "10px 20px" }}>
            <span style={{ width: 9, height: 9, borderRadius: 5, background: C.primary, opacity: 0.6 + 0.4 * Math.sin(frame / 5) }} />
            Live for Luma Hair Studio
          </Pill>
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 2. problem

export function ProblemScene() {
  const frame = useCurrentFrame();
  const swap = interpolate(frame, [70, 90], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const calls = ["10:42 AM", "1:15 PM", "7:58 PM", "9:20 PM"];
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 140, top: 330, width: 900 }}>
        <Title
          eyebrow="The problem"
          title={<>Every missed call<br />is a lost booking.</>}
          sub="Busy with a client, closed for the night, on lunch — callers don't leave voicemails. They book somewhere else."
          size={84}
        />
      </div>
      <div style={{ position: "absolute", right: 160, top: 290, width: 600, display: "flex", flexDirection: "column", gap: 20 }}>
        {calls.map((t, i) => {
          const p = interpolate(frame - 10 - i * 9, [0, 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
          return (
            <div
              key={t}
              style={{
                opacity: p,
                transform: `translateX(${(1 - p) * 60}px)`,
                background: "white",
                border: `1px solid ${C.border}`,
                borderRadius: 22,
                padding: "22px 26px",
                display: "flex",
                alignItems: "center",
                gap: 18,
                boxShadow: "0 20px 50px -30px rgba(11,27,51,0.35)",
              }}
            >
              <div
                style={{
                  width: 54,
                  height: 54,
                  borderRadius: 27,
                  background: swap > 0.5 ? C.mint : "#ffdad6",
                  color: swap > 0.5 ? C.primary : C.error,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 26,
                  fontWeight: 800,
                }}
              >
                {swap > 0.5 ? "✓" : "✕"}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 26, fontWeight: 700, color: C.text }}>{swap > 0.5 ? "Answered by Ava" : "Missed call"}</div>
                <div style={{ fontSize: 20, color: C.muted }}>
                  {t} · {swap > 0.5 ? ["Booked haircut", "Answered FAQ", "Booked colour", "Took a message"][i] : "No voicemail"}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 3. landing

export function LandingScene() {
  const rot = useCamera(-14, -6, 150);
  const scale = useCamera(0.94, 1.02, 150);
  const enter = useEnter(0, 30);
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 120, top: 300, width: 560 }}>
        <Title
          eyebrow="Answers everywhere"
          title="Phone or website, Ava picks up"
          sub="Callers tap “Talk to the receptionist” on your site — or simply call your number."
          size={60}
        />
      </div>
      <div
        style={{
          position: "absolute",
          left: 720,
          top: 150,
          perspective: 1800,
          opacity: enter,
        }}
      >
        <div style={{ transform: `rotateY(${rot}deg) scale(${scale})`, transformOrigin: "left center" }}>
          <BrowserFrame src="shots/01-landing.png" url="luma-hair.receptly.app" width={1320} />
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 5. booked

export function BookedScene() {
  const frame = useCurrentFrame();
  const W = 1480;
  const L = 120;
  const T = 230;
  const cropTop = 390;
  const m = mapper(L, T, W, cropTop);
  const push = useCamera(1, 1.04, 180);
  const email = interpolate(frame, [40, 62], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const cal = interpolate(frame, [20, 40], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 120, top: 70 }}>
        <Title eyebrow="Instant results" title="Booked straight into the calendar" size={56} />
      </div>
      <div style={{ position: "absolute", left: L, top: T, transform: `scale(${push})`, transformOrigin: "30% 30%" }}>
        <BrowserFrame src="shots/07-appointments.png" url="luma-hair.receptly.app/dashboard/appointments" width={W} crop={{ top: (cropTop * W) / 2000, height: 760 }} />
      </div>
      <Callout {...m(500, 538, 406, 52)} label="✦ Booked by AI — no double bookings" delay={70} side="bottom" />
      <div
        style={{
          position: "absolute",
          right: 110,
          top: 250 + (1 - cal) * 30,
          opacity: cal,
          background: "white",
          borderRadius: 20,
          padding: "18px 22px",
          display: "flex",
          alignItems: "center",
          gap: 14,
          boxShadow: "0 30px 60px -24px rgba(11,27,51,0.45)",
          border: `1px solid ${C.border}`,
          width: 460,
        }}
      >
        <div style={{ width: 52, height: 52, borderRadius: 14, background: "#e8f0fe", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28 }}>📅</div>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: C.text }}>Google Calendar</div>
          <div style={{ fontSize: 18, color: C.muted }}>Event created · Haircut – Ayesha Khan</div>
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          right: 110,
          bottom: 120 - (1 - email) * 40,
          opacity: email,
          width: 520,
          background: "white",
          borderRadius: 22,
          padding: "24px 26px",
          boxShadow: "0 40px 80px -30px rgba(11,27,51,0.5)",
          border: `1px solid ${C.border}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 22, background: C.mint, color: C.primary, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 }}>✉</div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>Luma Hair Studio</div>
            <div style={{ fontSize: 15, color: C.muted }}>to ayesha.k@example.com · now</div>
          </div>
        </div>
        <div style={{ fontSize: 21, fontWeight: 700, marginBottom: 6 }}>Your appointment is confirmed</div>
        <div style={{ fontSize: 18, color: C.muted, lineHeight: 1.45 }}>
          Hi Ayesha, you&apos;re booked for a Haircut with Sara tomorrow at 2:30 PM. Need to change it? Just call — Ava will help.
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 6. overview

export function OverviewScene() {
  const W = 1560;
  const L = 180;
  const T = 190;
  const m = mapper(L, T, W);
  const zoom = useCamera(1, 1.06, 240);
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 180, top: 56 }}>
        <Title eyebrow="Dashboard" title="See every call, booking and result" size={54} />
      </div>
      <div style={{ position: "absolute", left: L, top: T, transform: `scale(${zoom})`, transformOrigin: "50% 0%" }}>
        <BrowserFrame src="shots/04-overview.png" url="luma-hair.receptly.app/dashboard" width={W} crop={{ height: 860 }} />
      </div>
      <Callout {...m(795, 213, 371, 213)} label="Appointments booked by AI" delay={40} side="bottom" />
      <Callout {...m(1310, 720, 645, 420)} label="Every call summarised" delay={110} side="top" />
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 7. call detail

export function CallDetailScene() {
  const W = 1560;
  const L = 180;
  const T = 190;
  const m = mapper(L, T, W);
  const pan = useCamera(0, -120, 240);
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 180, top: 56 }}>
        <Title eyebrow="Full transparency" title="Transcript, tools and response time" size={54} />
      </div>
      <div style={{ position: "absolute", left: L, top: T + pan * 0 }}>
        <BrowserFrame src="shots/06-call-detail.png" url="luma-hair.receptly.app/dashboard/calls/…" width={W} crop={{ height: 780 }} />
      </div>
      <Callout {...m(490, 768, 740, 36)} label="Real calendar check, logged" delay={36} side="bottom" />
      <Callout {...m(1265, 230, 662, 114)} label="Sub-second replies" delay={96} side="bottom" />
      <Callout {...m(1346, 402, 610, 212)} label="AI summary for staff" delay={156} side="left" />
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 8. knowledge + settings

export function TeachScene() {
  const frame = useCurrentFrame();
  const a = useEnter(0, 30);
  const b = interpolate(frame, [30, 60], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 120, top: 56 }}>
        <Title eyebrow="Your business, your rules" title="Teach Ava in minutes — no code" size={54} />
      </div>
      <div style={{ position: "absolute", left: 120, top: 230, opacity: a, transform: `translateY(${(1 - a) * 40}px) rotate(-1.5deg)` }}>
        <BrowserFrame src="shots/09-knowledge.png" url="…/dashboard/knowledge" width={1000} />
      </div>
      <div style={{ position: "absolute", right: 110, top: 330, opacity: b, transform: `translateY(${(1 - b) * 60}px) rotate(1.5deg)` }}>
        <BrowserFrame src="shots/10-settings.png" url="…/dashboard/settings" width={880} />
      </div>
      <div style={{ position: "absolute", left: 140, bottom: 70, display: "flex", gap: 16, opacity: b }}>
        {["FAQs & prices", "Opening hours", "Services & buffers", "Greeting & voice", "Handoff number"].map((t) => (
          <Pill key={t} bg="white" color={C.text} style={{ border: `1px solid ${C.border}`, fontSize: 20, padding: "10px 18px" }}>
            ✓ {t}
          </Pill>
        ))}
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 9. guarantees

export function GuaranteesScene() {
  const frame = useCurrentFrame();
  const cards = [
    { big: "0", label: "double bookings", sub: "20 callers grab the same slot → exactly 1 booking" },
    { big: "0", label: "invented times", sub: "Ava can only offer slots the calendar returned" },
    { big: "30/30", label: "test scenarios passed", sub: "Bookings, changes, FAQs, handoffs, guardrails" },
    { big: "24/7", label: "always answered", sub: "Nights, weekends, busy hours — plus instant human handoff" },
  ];
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop dark />
      <div style={{ position: "absolute", left: 140, top: 190 }}>
        <Title dark eyebrow="Built to be trusted" title="Reliable by design" sub="Rules enforced by the system, not just the AI — and verified by an automated test suite." size={68} />
      </div>
      <div style={{ position: "absolute", left: 140, right: 140, top: 560, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 26 }}>
        {cards.map((c, i) => {
          const p = interpolate(frame - 30 - i * 12, [0, 22], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
          return (
            <div
              key={c.label}
              style={{
                opacity: p,
                transform: `translateY(${(1 - p) * 40}px)`,
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.14)",
                borderRadius: 26,
                padding: "30px 28px",
                minHeight: 260,
              }}
            >
              <div style={{ fontSize: 84, fontWeight: 800, color: C.primaryFixed, letterSpacing: "-0.04em", lineHeight: 1 }}>{c.big}</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: "white", marginTop: 12 }}>{c.label}</div>
              <div style={{ fontSize: 20, color: "rgba(255,255,255,0.7)", marginTop: 10, lineHeight: 1.4 }}>{c.sub}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 10. mobile + handoff

export function MobileScene() {
  const a = useSpring(0, 16);
  const b = useEnter(20, 26);
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 140, top: 300, width: 760 }}>
        <Title
          eyebrow="Anywhere"
          title="Your front desk, in your pocket"
          sub="Check calls, callbacks and today's bookings from your phone between clients."
          size={64}
        />
      </div>
      <div style={{ position: "absolute", right: 520, top: 110, transform: `translateY(${(1 - a) * 200}px) rotate(-4deg)` }}>
        <PhoneFrame src="shots/11-mobile-overview.png" height={860} />
      </div>
      <div style={{ position: "absolute", right: 110, top: 300, opacity: b, transform: `translateX(${(1 - b) * 40}px)`, width: 420 }}>
        <div style={{ background: "white", borderRadius: 22, padding: "22px 24px", boxShadow: "0 30px 60px -24px rgba(11,27,51,0.45)", borderLeft: `6px solid ${C.error}` }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: C.error, letterSpacing: "0.08em" }}>URGENT · WANTS A PERSON</div>
          <div style={{ fontSize: 24, fontWeight: 700, marginTop: 6 }}>Bilal Ahmed</div>
          <div style={{ fontSize: 18, color: C.muted, marginTop: 6, lineHeight: 1.4 }}>“Can someone call me about a bridal package for Saturday?”</div>
          <div style={{ marginTop: 14 }}>
            <Pill>Staff notified by email</Pill>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 11. outro

export function OutroScene() {
  const s = useSpring(0, 14);
  const t = useEnter(14, 26);
  const u = useEnter(34, 26);
  return (
    <AbsoluteFill style={{ fontFamily, alignItems: "center", justifyContent: "center" }}>
      <Backdrop dark />
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 26, textAlign: "center" }}>
        <div style={{ transform: `scale(${0.6 + 0.4 * s})`, opacity: s }}>
          <BrandMark size={110} />
        </div>
        <div style={{ opacity: t, transform: `translateY(${(1 - t) * 20}px)`, fontSize: 92, fontWeight: 800, color: "white", letterSpacing: "-0.04em" }}>
          Never miss a call again.
        </div>
        <div style={{ opacity: t, fontSize: 34, color: "rgba(255,255,255,0.8)" }}>Answers · Books · Hands off — 24/7</div>
        <div style={{ opacity: u, marginTop: 26, display: "flex", gap: 14 }}>
          {["LiveKit", "Gemini Live", "Google Calendar", "FastAPI", "Next.js"].map((x) => (
            <span key={x} style={{ border: "1px solid rgba(255,255,255,0.25)", color: "rgba(255,255,255,0.85)", borderRadius: 999, padding: "8px 18px", fontSize: 20 }}>
              {x}
            </span>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
}
