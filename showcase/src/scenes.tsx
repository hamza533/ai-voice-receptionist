import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

import {
  Backdrop,
  BrandMark,
  BrowserFrame,
  Callout,
  Pill,
  RingingPhone,
  SmsPhone,
  Title,
  ease,
  useEnter,
  useSpring,
} from "./components";
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

function useCamera(from: number, to: number, frames: number, delay = 0) {
  const frame = useCurrentFrame();
  return interpolate(frame - delay, [0, frames], [from, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
}

function Notice({ at, title, sub, tone = "error" }: { at: number; title: string; sub: string; tone?: "error" | "ok" }) {
  const frame = useCurrentFrame();
  const p = interpolate(frame - at, [0, 16], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return (
    <div
      style={{
        opacity: p,
        transform: `translateX(${(1 - p) * 50}px)`,
        background: "white",
        border: `1px solid ${C.border}`,
        borderRadius: 20,
        padding: "16px 20px",
        display: "flex",
        alignItems: "center",
        gap: 16,
        boxShadow: "0 20px 50px -30px rgba(11,27,51,0.35)",
        fontFamily,
      }}
    >
      <div
        style={{
          width: 46,
          height: 46,
          borderRadius: 23,
          background: tone === "ok" ? C.mint : "#ffdad6",
          color: tone === "ok" ? C.primary : C.error,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 22,
          fontWeight: 800,
          flexShrink: 0,
        }}
      >
        {tone === "ok" ? "✓" : "✕"}
      </div>
      <div>
        <div style={{ fontSize: 22, fontWeight: 700, color: C.text }}>{title}</div>
        <div style={{ fontSize: 18, color: C.muted }}>{sub}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 1. the Saturday rush

export function HookScene() {
  const phone = useSpring(2, 16);
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 140, top: 300, width: 860 }}>
        <Title eyebrow="Saturday, 11:40 AM" title={<>Every chair is full.<br />The phone keeps ringing.</>} size={80} />
      </div>
      <div style={{ position: "absolute", right: 560, top: 120, transform: `translateY(${(1 - phone) * 160}px)`, opacity: Math.min(1, phone * 1.5) }}>
        <RingingPhone width={330} />
      </div>
      <div style={{ position: "absolute", right: 80, top: 260, width: 380, display: "flex", flexDirection: "column", gap: 16 }}>
        <Notice at={28} title="Missed call" sub="10:42 AM · no voicemail" />
        <Notice at={48} title="Missed call" sub="11:15 AM · no voicemail" />
        <Notice at={68} title="Missed call" sub="11:38 AM · no voicemail" />
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 2. what it costs

export function CostScene() {
  const frame = useCurrentFrame();
  const rows = [
    { t: "10:42 AM", who: "Haircut enquiry" },
    { t: "11:15 AM", who: "Colour appointment" },
    { t: "11:38 AM", who: "Kids haircut, today" },
    { t: "12:05 PM", who: "Bridal styling" },
  ];
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 140, top: 320, width: 880 }}>
        <Title eyebrow="The real cost" title={<>Every missed call<br />is a customer lost.</>} sub="Callers rarely leave a message. They simply book with someone who answers." size={78} />
      </div>
      <div style={{ position: "absolute", right: 110, top: 250, width: 700, display: "flex", flexDirection: "column", gap: 18 }}>
        {rows.map((r, i) => {
          const p = interpolate(frame - 2 - i * 6, [0, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
          const lost = interpolate(frame - 30 - i * 7, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
          return (
            <div key={r.t} style={{ opacity: p, transform: `translateX(${(1 - p) * 60}px)`, background: "white", border: `1px solid ${C.border}`, borderRadius: 22, padding: "20px 24px", display: "flex", alignItems: "center", gap: 18, boxShadow: "0 20px 50px -30px rgba(11,27,51,0.35)" }}>
              <div style={{ width: 50, height: 50, borderRadius: 25, background: "#ffdad6", color: C.error, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, fontWeight: 800 }}>✕</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 24, fontWeight: 700, color: C.text, whiteSpace: "nowrap" }}>Missed call · {r.t}</div>
                <div style={{ fontSize: 19, color: C.muted }}>{r.who}</div>
              </div>
              <div style={{ opacity: lost, transform: `scale(${0.8 + 0.2 * lost})`, background: "#fff1f0", color: C.error, border: "1px solid #ffc9c4", borderRadius: 999, padding: "6px 14px", fontSize: 17, fontWeight: 700, whiteSpace: "nowrap" }}>
                Booked elsewhere
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 3. meet Ava

export function IntroScene() {
  const frame = useCurrentFrame();
  const s = useSpring(2, 14);
  const word = useEnter(8, 20);
  const tag = useEnter(18, 20);
  const chips = ["Answers every call", "Day and night", "Warm, natural voice", "Books, reminds, refills"];
  return (
    <AbsoluteFill style={{ fontFamily, alignItems: "center", justifyContent: "center" }}>
      <Backdrop dark />
      <div style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center", gap: 26 }}>
        <div style={{ transform: `scale(${0.4 + 0.6 * s}) rotate(${(1 - s) * -20}deg)`, opacity: Math.min(1, s * 2) }}>
          <BrandMark size={130} />
        </div>
        <div style={{ opacity: word, transform: `translateY(${(1 - word) * 24}px)`, fontSize: 100, fontWeight: 800, color: "white", letterSpacing: "-0.04em" }}>
          Meet Ava
        </div>
        <div style={{ opacity: tag, transform: `translateY(${(1 - tag) * 18}px)`, fontSize: 36, color: "rgba(255,255,255,0.82)", fontWeight: 500 }}>
          Your receptionist from <b style={{ color: C.primaryFixed }}>Receptly</b>
        </div>
        <div style={{ display: "flex", gap: 14, marginTop: 10 }}>
          {chips.map((c, i) => {
            const p = interpolate(frame - 30 - i * 7, [0, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
            return (
              <span key={c} style={{ opacity: p, transform: `translateY(${(1 - p) * 14}px)`, border: "1px solid rgba(255,255,255,0.25)", color: "rgba(255,255,255,0.9)", borderRadius: 999, padding: "10px 20px", fontSize: 22 }}>
                ✓ {c}
              </span>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 5. booked and confirmed

export function ConfirmScene() {
  const frame = useCurrentFrame();
  const W = 1180;
  const L = 110;
  const T = 250;
  const push = useCamera(1, 1.04, 200);
  const cal = interpolate(frame, [12, 28], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 110, top: 70 }}>
        <Title eyebrow="Seconds later" title="Booked, and confirmed by text" size={56} />
      </div>
      <div style={{ position: "absolute", left: L, top: T, transform: `scale(${push})`, transformOrigin: "30% 30%" }}>
        <BrowserFrame src="shots/07-appointments.png" url="luma-hair.receptly.app/dashboard/appointments" width={W} crop={{ top: (360 * W) / 2000, height: 620 }} />
      </div>
      <div style={{ position: "absolute", left: 640, top: 790 - (1 - cal) * 30, opacity: cal, background: "white", borderRadius: 18, padding: "14px 20px", display: "flex", alignItems: "center", gap: 14, boxShadow: "0 30px 60px -24px rgba(11,27,51,0.45)", border: `1px solid ${C.border}` }}>
        <div style={{ width: 44, height: 44, borderRadius: 12, background: C.mint, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24 }}>📅</div>
        <div>
          <div style={{ fontSize: 19, fontWeight: 700, color: C.text }}>Added to your calendar</div>
          <div style={{ fontSize: 16, color: C.muted }}>Haircut · Ayesha Khan · Thu 2:30 PM · Sara</div>
        </div>
      </div>
      <div style={{ position: "absolute", right: 150, top: 150 }}>
        <SmsPhone
          contact="Luma Hair Studio"
          width={340}
          messages={[{ at: 20, from: "business", text: "Luma Hair Studio: You're booked: Haircut with Sara, Thu 26 Nov at 2:30 PM. Reply C to cancel." }]}
        />
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 6. reminders + waitlist

export function WaitlistScene() {
  const frame = useCurrentFrame();
  const bridge = interpolate(frame, [74, 88], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 0, right: 0, top: 60, display: "flex", justifyContent: "center" }}>
        <Title align="center" eyebrow="Fewer no-shows" title="Cancelled? Offered to the next person in line." size={54} />
      </div>
      <div style={{ position: "absolute", left: 270, top: 172 }}>
        <div style={{ textAlign: "center", fontSize: 20, fontWeight: 700, color: C.muted, marginBottom: 12 }}>Bilal · the day before</div>
        <SmsPhone
          contact="Luma Hair Studio"
          width={300}
          messages={[
            { at: 8, from: "business", text: "Reminder from Luma Hair Studio: Haircut with Sara, Thu 26 Nov at 2:30 PM. Reply C to cancel." },
            { at: 42, from: "customer", text: "C" },
            { at: 58, from: "business", text: "Luma Hair Studio: your Haircut on Thu 26 Nov at 2:30 PM is cancelled." },
          ]}
        />
      </div>
      <div style={{ position: "absolute", left: 760, top: 470, width: 400, display: "flex", flexDirection: "column", alignItems: "center", gap: 14, opacity: bridge, transform: `scale(${0.9 + 0.1 * bridge})` }}>
        <div style={{ fontSize: 64, color: C.brand }}>→</div>
        <div style={{ background: C.navy, color: "white", borderRadius: 16, padding: "14px 20px", fontSize: 22, fontWeight: 600, textAlign: "center", lineHeight: 1.35 }}>
          2:30 PM is free again
          <div style={{ fontSize: 17, fontWeight: 500, color: "rgba(255,255,255,0.75)" }}>Offered to the waitlist, held 30 min</div>
        </div>
      </div>
      <div style={{ position: "absolute", right: 270, top: 172 }}>
        <div style={{ textAlign: "center", fontSize: 20, fontWeight: 700, color: C.muted, marginBottom: 12 }}>Hina · on the waitlist</div>
        <SmsPhone
          contact="Luma Hair Studio"
          width={300}
          messages={[
            { at: 96, from: "business", text: "Luma Hair Studio: good news, Haircut with Sara is free Thu 26 Nov at 2:30 PM. Reply YES within 30 minutes to book it." },
            { at: 132, from: "customer", text: "YES" },
            { at: 148, from: "business", text: "Luma Hair Studio: booked! Haircut with Sara, Thu 26 Nov at 2:30 PM. Reply C to cancel." },
          ]}
        />
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 7. who's working

export function TeamScene() {
  const W = 1400;
  const L = 140;
  const T = 230;
  // Hold on the working hours, then scroll down to the time off.
  const scroll = useCamera(560, 1260, 90, 70);
  const a = useEnter(10, 16);
  const b = useEnter(120, 16);
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 140, top: 70 }}>
        <Title eyebrow="Team-aware" title="Knows who's working, and when" size={56} />
      </div>
      <div style={{ position: "absolute", left: L, top: T }}>
        <BrowserFrame src="shots/12-team-full.png" url="luma-hair.receptly.app/dashboard/team" width={W} crop={{ top: (scroll * W) / 2000, height: 760 }} />
      </div>
      <div style={{ position: "absolute", right: 90, top: 380, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ opacity: a, transform: `translateX(${(1 - a) * 30}px)` }}>
          <Pill bg={C.navy} color="white" style={{ fontSize: 22, padding: "12px 20px" }}>Sara&apos;s own hours</Pill>
        </div>
        <div style={{ opacity: b, transform: `translateX(${(1 - b) * 30}px)` }}>
          <Pill bg={C.navy} color="white" style={{ fontSize: 22, padding: "12px 20px" }}>Lunch & days off</Pill>
        </div>
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 8. what Ava brought in

export function ValueScene() {
  const W = 1560;
  const L = 180;
  const T = 190;
  const m = mapper(L, T, W);
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 180, top: 56 }}>
        <Title eyebrow="Your dashboard" title="See exactly what Ava brought in" size={54} />
      </div>
      <div style={{ position: "absolute", left: L, top: T }}>
        <BrowserFrame src="shots/04-overview.png" url="luma-hair.receptly.app/dashboard" width={W} crop={{ height: 860 }} />
      </div>
      <Callout {...m(795, 213, 372, 262)} label="Booked by Ava this week" delay={14} side="right" />
      <Callout {...m(401, 213, 371, 262)} label="Answered while you were closed" delay={52} side="bottom" />
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 9. safeguards

export function TrustScene() {
  const frame = useCurrentFrame();
  const cards = [
    { big: "0", label: "double bookings", sub: "Two customers never get the same time" },
    { big: "✓", label: "only real free times", sub: "Ava never guesses or makes up a time" },
    { big: "→", label: "a person when needed", sub: "Callers who ask are passed to your team" },
    { big: "24/7", label: "always answered", sub: "Evenings, weekends and busy Saturdays" },
  ];
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop dark />
      <div style={{ position: "absolute", left: 140, top: 190 }}>
        <Title dark eyebrow="Peace of mind" title="Reliable on every call" sub="Your calendar stays accurate, and your customers are always looked after." size={68} />
      </div>
      <div style={{ position: "absolute", left: 140, right: 140, top: 560, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 26 }}>
        {cards.map((c, i) => {
          const p = interpolate(frame - 14 - i * 9, [0, 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
          return (
            <div key={c.label} style={{ opacity: p, transform: `translateY(${(1 - p) * 40}px)`, background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.14)", borderRadius: 26, padding: "30px 28px", minHeight: 250 }}>
              <div style={{ fontSize: 80, fontWeight: 800, color: C.primaryFixed, letterSpacing: "-0.04em", lineHeight: 1 }}>{c.big}</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: "white", marginTop: 12 }}>{c.label}</div>
              <div style={{ fontSize: 20, color: "rgba(255,255,255,0.72)", marginTop: 10, lineHeight: 1.4 }}>{c.sub}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 10. ready in minutes

export function SetupScene() {
  const frame = useCurrentFrame();
  const steps = ["Business details", "Opening hours", "Your team", "Services & prices", "Calendar & texts", "Test call"];
  const enter = useEnter(0, 22);
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 120, top: 70 }}>
        <Title eyebrow="Easy to start" title="Ready in minutes, no tech skills" size={56} />
      </div>
      <div style={{ position: "absolute", left: 120, top: 215, opacity: enter, transform: `translateY(${(1 - enter) * 40}px) rotate(-1deg)` }}>
        <BrowserFrame src="shots/14-setup.png" url="luma-hair.receptly.app/dashboard/setup" width={1030} />
      </div>
      <div style={{ position: "absolute", right: 120, top: 280, width: 470, display: "flex", flexDirection: "column", gap: 14 }}>
        {steps.map((s, i) => {
          const p = interpolate(frame - 10 - i * 12, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
          return (
            <div key={s} style={{ opacity: 0.35 + 0.65 * p, display: "flex", alignItems: "center", gap: 16, background: "white", border: `1px solid ${C.border}`, borderRadius: 18, padding: "16px 20px", boxShadow: "0 16px 40px -28px rgba(11,27,51,0.4)" }}>
              <div style={{ width: 36, height: 36, borderRadius: 18, background: p > 0.5 ? C.primary : C.surfaceContainer, color: "white", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 19, fontWeight: 800, transform: `scale(${0.85 + 0.15 * p})` }}>
                {p > 0.5 ? "✓" : ""}
              </div>
              <div style={{ fontSize: 24, fontWeight: 600, color: C.text }}>{s}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------- 11. outro

export function OutroScene() {
  const s = useSpring(0, 14);
  const t = useEnter(8, 20);
  const u = useEnter(24, 20);
  return (
    <AbsoluteFill style={{ fontFamily, alignItems: "center", justifyContent: "center" }}>
      <Backdrop dark />
      <div style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center", gap: 24, textAlign: "center" }}>
        <div style={{ transform: `scale(${0.6 + 0.4 * s})`, opacity: s }}>
          <BrandMark size={110} />
        </div>
        <div style={{ opacity: t, transform: `translateY(${(1 - t) * 20}px)`, fontSize: 30, fontWeight: 700, color: C.primaryFixed, letterSpacing: "0.12em", textTransform: "uppercase" }}>
          Receptly
        </div>
        <div style={{ opacity: t, transform: `translateY(${(1 - t) * 20}px)`, fontSize: 84, fontWeight: 800, color: "white", letterSpacing: "-0.04em", lineHeight: 1.05 }}>
          Never miss a call,<br />or a customer, again.
        </div>
        <div style={{ opacity: u, marginTop: 20, display: "flex", gap: 14 }}>
          {["Answers every call", "Books your calendar", "Texts & reminders", "Fills cancellations"].map((x) => (
            <span key={x} style={{ background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.3)", color: "white", borderRadius: 999, padding: "10px 22px", fontSize: 22, fontWeight: 500 }}>
              {x}
            </span>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
}
