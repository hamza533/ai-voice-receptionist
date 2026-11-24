// The in-call screen of the app (web call), animated to a scripted booking conversation.
// Same layout and tokens as web/src/components/call/live-call.tsx.
import React from "react";
import { AbsoluteFill, interpolate, Sequence, staticFile, useCurrentFrame } from "remotion";
import { Audio } from "@remotion/media";

import { Backdrop, Title, ease, useEnter } from "./components";
import { C, fontFamily } from "./theme";

import { audioFile, callTimeline, type CallLine } from "./vo";

type Line = CallLine;
const { lines: LINES, tools: TOOLS, end: CALL_END } = callTimeline();
export { CALL_END };

function speakingNow(frame: number) {
  return LINES.some((l) => l.who === "agent" && frame >= l.at && frame < l.at + l.frames);
}

function Bubble({ line }: { line: Line }) {
  const frame = useCurrentFrame();
  const p = interpolate(frame - line.at, [0, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  // Text reveals in step with the spoken clip.
  const chars = Math.floor(interpolate(frame - line.at, [0, Math.max(8, line.frames * 0.92)], [0, line.text.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const caller = line.who === "caller";
  if (frame < line.at) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: caller ? "flex-end" : "flex-start", gap: 6, opacity: p, transform: `translateY(${(1 - p) * 14}px)` }}>
      {!caller ? (
        <span style={{ background: C.primary, color: "white", fontSize: 13, fontWeight: 700, borderRadius: 6, padding: "3px 8px" }}>✦ Ava</span>
      ) : (
        <span style={{ color: C.muted, fontSize: 14 }}>Ayesha</span>
      )}
      <div
        style={{
          maxWidth: "86%",
          background: caller ? C.surfaceLow : C.mint,
          borderRadius: 20,
          borderTopRightRadius: caller ? 6 : 20,
          borderTopLeftRadius: caller ? 20 : 6,
          padding: "14px 18px",
          fontSize: 21,
          lineHeight: 1.45,
          color: C.text,
        }}
      >
        {line.text.slice(0, chars)}
      </div>
    </div>
  );
}

function Orb({ speaking }: { speaking: boolean }) {
  const frame = useCurrentFrame();
  const ring = (offset: number) => {
    const t = ((frame + offset) % 72) / 72;
    return { transform: `scale(${0.85 + t * 0.55})`, opacity: (1 - t) * 0.55 };
  };
  return (
    <div style={{ position: "relative", width: 300, height: 300, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", inset: 0, borderRadius: "50%", background: C.primaryFixed, ...ring(0) }} />
      <div style={{ position: "absolute", inset: 0, borderRadius: "50%", background: C.primaryFixed, ...ring(36) }} />
      <div style={{ position: "absolute", inset: 28, borderRadius: "50%", background: C.mint }} />
      <div
        style={{
          position: "relative",
          width: 190,
          height: 190,
          borderRadius: "50%",
          background: `linear-gradient(180deg, ${C.primaryContainer}, ${C.primary})`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 9,
          transform: `scale(${speaking ? 1.04 + Math.sin(frame / 3) * 0.015 : 1})`,
          boxShadow: "0 24px 60px -20px rgba(0,104,91,0.8)",
        }}
      >
        {[0.45, 0.8, 1, 0.7, 0.5].map((h, i) => {
          const amp = speaking ? 0.45 + 0.55 * Math.abs(Math.sin(frame / (3.2 + i * 0.6) + i)) : 0.35;
          return <span key={i} style={{ width: 11, height: 70 * h * amp + 10, borderRadius: 6, background: "white" }} />;
        })}
      </div>
    </div>
  );
}

export function LiveCallScene() {
  const frame = useCurrentFrame();
  const enter = useEnter(0, 30);
  const speaking = speakingNow(frame);
  const secs = Math.floor(frame / 30) + 3;
  const timer = `00:${String(secs).padStart(2, "0")}`;
  const status = speaking ? "Speaking" : TOOLS.some((t) => frame >= t.at && frame < t.done) ? "Thinking" : "Listening";

  return (
    <AbsoluteFill style={{ fontFamily }}>
      <Backdrop />
      <div style={{ position: "absolute", left: 120, top: 70 }}>
        <Title eyebrow="A real call" title="Ava books it in under a minute" size={52} />
      </div>
      <div
        style={{
          position: "absolute",
          left: 120,
          right: 120,
          top: 230,
          bottom: 70,
          display: "grid",
          gridTemplateColumns: "0.9fr 1.1fr",
          gap: 32,
          opacity: enter,
          transform: `translateY(${(1 - enter) * 40}px)`,
        }}
      >
        {/* Left: call card */}
        <div style={{ background: "white", borderRadius: 28, border: `1px solid ${C.border}`, boxShadow: "0 30px 80px -40px rgba(11,27,51,0.35)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 22 }}>
          <div style={{ color: C.primary, fontWeight: 700, letterSpacing: "0.1em", fontSize: 17 }}>LUMA HAIR STUDIO · LINE 01</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, background: C.surfaceLow, borderRadius: 999, padding: "8px 18px", fontSize: 20, fontWeight: 500 }}>
            <span style={{ width: 10, height: 10, borderRadius: 5, background: "#10b981" }} />
            Connected — {status}…
            <span style={{ color: C.primary, fontVariantNumeric: "tabular-nums" }}>{timer}</span>
          </div>
          <Orb speaking={speaking} />
          <div style={{ display: "flex", gap: 40, marginTop: 6 }}>
            {[
              { label: "Mute", bg: C.surfaceContainer, color: C.text, icon: "🎙" },
              { label: "End call", bg: C.error, color: "white", icon: "✆" },
            ].map((b) => (
              <div key={b.label} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, fontSize: 16, fontWeight: 500 }}>
                <div style={{ width: 64, height: 64, borderRadius: 32, background: b.bg, color: b.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 26 }}>{b.icon}</div>
                {b.label}
              </div>
            ))}
          </div>
        </div>

        {/* Right: transcript + actions */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24, minHeight: 0 }}>
          <div style={{ flex: 1, minHeight: 0, background: "white", borderRadius: 28, border: `1px solid ${C.border}`, boxShadow: "0 30px 80px -40px rgba(11,27,51,0.35)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "20px 26px", borderBottom: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 22, fontWeight: 700 }}>💬 The conversation</div>
              <span style={{ background: C.mint, color: C.primary, borderRadius: 999, padding: "4px 12px", fontSize: 15, fontWeight: 700 }}>● Live</span>
            </div>
            <div style={{ position: "relative", flex: 1, overflow: "hidden" }}>
              {/* Bottom-anchored: new lines push older ones up and out, like a chat. */}
              <div style={{ position: "absolute", left: 26, right: 26, bottom: 22, display: "flex", flexDirection: "column", gap: 16 }}>
                {LINES.map((l) => (
                  <Bubble key={l.id} line={l} />
                ))}
              </div>
            </div>
          </div>
          <div style={{ background: "white", borderRadius: 28, border: `1px solid ${C.border}`, padding: "20px 26px", boxShadow: "0 30px 80px -40px rgba(11,27,51,0.35)" }}>
            <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 14 }}>✦ What Ava is doing</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12, minHeight: 150 }}>
              {TOOLS.filter((t) => frame >= t.at).map((t) => {
                const done = frame >= t.done;
                const p = interpolate(frame - t.at, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                return (
                  <div key={t.label} style={{ display: "flex", alignItems: "center", gap: 14, opacity: p }}>
                    <div style={{ width: 30, height: 30, borderRadius: 15, background: done ? C.primary : C.surfaceContainer, color: "white", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 17, fontWeight: 800 }}>
                      {done ? "✓" : <span style={{ width: 14, height: 14, borderRadius: 7, border: `3px solid ${C.primary}`, borderTopColor: "transparent", transform: `rotate(${frame * 18}deg)` }} />}
                    </div>
                    <div>
                      <div style={{ fontSize: 20, fontWeight: 600 }}>{t.label}</div>
                      <div style={{ fontSize: 16, color: C.muted }}>{done ? t.detail : "Working…"}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
      {TOOLS.slice(1, 2).map((t) => (
        <Sequence key={t.label} from={t.done}>
          <Audio src="https://remotion.media/ding.wav" volume={0.3} />
        </Sequence>
      ))}
      {LINES.map((l) => (
        <Sequence key={`a-${l.id}`} from={l.at} durationInFrames={l.frames + 6}>
          {/* Caller audio sounds a little "phone-like" next to Ava's studio-clean voice. */}
          <Audio src={staticFile(audioFile(l.id))} volume={l.who === "caller" ? 0.85 : 1} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}
