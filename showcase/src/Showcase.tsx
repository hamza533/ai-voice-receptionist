import { Audio } from "@remotion/media";
import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import React from "react";
import { AbsoluteFill, interpolate, Sequence, staticFile } from "remotion";

import { LiveCallScene } from "./LiveCallScene";
import {
  BookedScene,
  CallDetailScene,
  GuaranteesScene,
  IntroScene,
  LandingScene,
  MobileScene,
  OutroScene,
  OverviewScene,
  ProblemScene,
  TeachScene,
} from "./scenes";

export const SCENES: { id: string; frames: number; el: React.ReactNode }[] = [
  { id: "intro", frames: 110, el: <IntroScene /> },
  { id: "problem", frames: 150, el: <ProblemScene /> },
  { id: "landing", frames: 150, el: <LandingScene /> },
  { id: "call", frames: 600, el: <LiveCallScene /> },
  { id: "booked", frames: 180, el: <BookedScene /> },
  { id: "overview", frames: 210, el: <OverviewScene /> },
  { id: "detail", frames: 240, el: <CallDetailScene /> },
  { id: "teach", frames: 180, el: <TeachScene /> },
  { id: "guarantees", frames: 200, el: <GuaranteesScene /> },
  { id: "mobile", frames: 150, el: <MobileScene /> },
  { id: "outro", frames: 170, el: <OutroScene /> },
];

export const T = 14; // transition length in frames
export const TOTAL = SCENES.reduce((s, x) => s + x.frames, 0) - T * (SCENES.length - 1);

export function Showcase() {
  // Cut points (start frame of each scene after the first) for whoosh sound effects.
  const cuts: number[] = [];
  let acc = 0;
  SCENES.forEach((s, i) => {
    if (i > 0) cuts.push(acc - T);
    acc += s.frames - (i > 0 ? T : 0);
  });
  return (
    <AbsoluteFill style={{ background: "#f8f9ff" }}>
      <TransitionSeries>
        {SCENES.flatMap((s, i) => {
          const seq = (
            <TransitionSeries.Sequence key={s.id} name={s.id} durationInFrames={s.frames}>
              {s.el}
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
      <Audio
        src={staticFile("music.wav")}
        volume={(f) => interpolate(f, [0, 30, TOTAL - 60, TOTAL], [0, 0.55, 0.55, 0], { extrapolateRight: "clamp" })}
      />
      {cuts.map((c, i) => (
        <Sequence key={c} from={Math.max(0, c)} durationInFrames={30}>
          <Audio src="https://remotion.media/whoosh.wav" volume={i % 2 ? 0.12 : 0.18} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}
