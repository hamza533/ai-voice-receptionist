import { Audio } from "@remotion/media";
import React from "react";
import { interpolate, Sequence, staticFile, useCurrentFrame } from "remotion";

import { fontFamily } from "./theme";
import { audioFile, clip, vf, type VoId } from "./vo";

/** Voiceover clip plus a burned-in caption shown while it plays. */
export function Narration({ id, from }: { id: VoId; from: number }) {
  const frames = vf(id);
  return (
    <Sequence from={from} durationInFrames={frames + 8} layout="none">
      <Audio src={staticFile(audioFile(id))} />
      <Caption text={clip(id).text} frames={frames} />
    </Sequence>
  );
}

function Caption({ text, frames }: { text: string; frames: number }) {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 6, frames, frames + 8], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 46,
        display: "flex",
        justifyContent: "center",
        opacity,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          maxWidth: 1500,
          background: "rgba(11, 27, 51, 0.82)",
          color: "white",
          fontFamily,
          fontWeight: 500,
          fontSize: 34,
          lineHeight: 1.35,
          textAlign: "center",
          padding: "14px 28px",
          borderRadius: 18,
          boxShadow: "0 20px 50px -20px rgba(11,27,51,0.6)",
        }}
      >
        {text}
      </div>
    </div>
  );
}
