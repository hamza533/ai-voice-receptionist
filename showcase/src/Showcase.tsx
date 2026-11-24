import { Audio } from "@remotion/media";
import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import React from "react";
import { AbsoluteFill, interpolate, Sequence, staticFile } from "remotion";

import { CALL_END, LiveCallScene } from "./LiveCallScene";
import { Narration } from "./Narration";
import {
  ConfirmScene,
  CostScene,
  HookScene,
  IntroScene,
  OutroScene,
  SetupScene,
  TeamScene,
  TrustScene,
  ValueScene,
  WaitlistScene,
} from "./scenes";
import { vf, type VoId } from "./vo";

type SceneDef = { id: string; el: React.ReactNode; vo?: VoId; lead?: number; tail?: number; min?: number };

// Problem first (the Saturday rush and what it costs), then Ava, then what she does for
// the business. Plain language only: no product internals on screen or in the voice.
const DEFS: SceneDef[] = [
  { id: "hook", el: <HookScene />, vo: "n_hook", lead: 6, tail: 12, min: 150 },
  { id: "cost", el: <CostScene />, vo: "n_cost", lead: 4, tail: 20, min: 120 },
  { id: "intro", el: <IntroScene />, vo: "n_intro", lead: 6, tail: 12 },
  { id: "call", el: <LiveCallScene />, min: CALL_END },
  { id: "confirm", el: <ConfirmScene />, vo: "n_confirm", lead: 4, tail: 26, min: 150 },
  { id: "waitlist", el: <WaitlistScene />, vo: "n_waitlist", lead: 4, tail: 18, min: 200 },
  { id: "team", el: <TeamScene />, vo: "n_team", lead: 4, tail: 16, min: 180 },
  { id: "value", el: <ValueScene />, vo: "n_value", lead: 4, tail: 22, min: 160 },
  { id: "trust", el: <TrustScene />, vo: "n_trust", lead: 6, tail: 16 },
  { id: "setup", el: <SetupScene />, vo: "n_setup", lead: 4, tail: 18, min: 150 },
  { id: "outro", el: <OutroScene />, vo: "n_outro", lead: 10, tail: 45, min: 130 },
];

export const T = 10; // transition length in frames

export const SCENES = DEFS.map((d) => ({
  ...d,
  frames: Math.max(d.min ?? 0, d.vo ? (d.lead ?? 0) + vf(d.vo) + (d.tail ?? 0) : 0),
}));

const STARTS = SCENES.map((_, i) => SCENES.slice(0, i).reduce((s, x) => s + x.frames, 0) - i * T);
export const TOTAL = SCENES.reduce((s, x) => s + x.frames, 0) - T * (SCENES.length - 1);

// Spans where someone is speaking: the music ducks under them.
const VOICE_SPANS: [number, number][] = SCENES.flatMap((s, i) => {
  if (s.id === "call") return [[STARTS[i], STARTS[i] + s.frames]];
  if (!s.vo) return [];
  const a = STARTS[i] + (s.lead ?? 0);
  return [[a, a + vf(s.vo)]];
});

function musicVolume(f: number) {
  const full = 0.5;
  const ducked = 0.13;
  const ramp = 10;
  let v = full;
  for (const [a, b] of VOICE_SPANS) {
    const inside = interpolate(f, [a - ramp, a, b, b + ramp], [0, 1, 1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    v = Math.min(v, full - (full - ducked) * inside);
  }
  const fade = interpolate(f, [0, 30, TOTAL - 60, TOTAL], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return v * fade;
}

export function Showcase() {
  return (
    <AbsoluteFill style={{ background: "#f8f9ff" }}>
      <TransitionSeries>
        {SCENES.flatMap((s, i) => {
          const seq = (
            <TransitionSeries.Sequence key={s.id} name={s.id} durationInFrames={s.frames}>
              {s.el}
              {s.vo ? <Narration id={s.vo} from={s.lead ?? 0} /> : null}
            </TransitionSeries.Sequence>
          );
          if (i === 0) return [seq];
          const presentation = i % 3 === 1 ? slide({ direction: "from-right" }) : fade();
          return [
            <TransitionSeries.Transition key={`t-${s.id}`} presentation={presentation} timing={linearTiming({ durationInFrames: T })} />,
            seq,
          ];
        })}
      </TransitionSeries>
      <Audio src={staticFile("music.wav")} volume={musicVolume} />
      {STARTS.slice(1).map((c, i) => (
        <Sequence key={c} from={Math.max(0, c)} durationInFrames={30}>
          <Audio src="https://remotion.media/whoosh.wav" volume={i % 2 ? 0.08 : 0.12} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}
