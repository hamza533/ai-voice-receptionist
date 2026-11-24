// Voiceover timing helpers. src/voiceover.json is written by scripts/voiceover.py.
import manifest from "./voiceover.json";

import { FPS } from "./theme";

export type VoId = keyof typeof manifest;
type Clip = { file: string; seconds: number; text: string; voice: string };

const M = manifest as Record<string, Clip>;

export function clip(id: VoId): Clip {
  return M[id];
}

/** Pace: the narration is played 10% faster and the call 6% faster than recorded. The
 * clips are time-stretched by render.sh (ffmpeg atempo, so the pitch stays natural). */
export const NARRATION_RATE = 1.1;
export const DIALOGUE_RATE = 1.06;

export function rate(id: VoId): number {
  return id.startsWith("n_") ? NARRATION_RATE : DIALOGUE_RATE;
}

/** The time-stretched copy of a clip (see render.sh). */
export function audioFile(id: VoId): string {
  return `vo/fast/${id}.wav`;
}

/** Clip length in frames at its playback rate (rounded up). */
export function vf(id: VoId): number {
  return Math.ceil((M[id].seconds / rate(id)) * FPS);
}

// ---------------------------------------------------------------- call scene timeline

export type CallLine = { id: VoId; at: number; frames: number; who: "agent" | "caller"; text: string };
export type CallTool = { at: number; done: number; label: string; detail: string };

/** Dialogue placed back to back with natural gaps; tool work sits between turns. */
export function callTimeline() {
  const order: { id: VoId; who: "agent" | "caller"; toolAfter?: { label: string; detail: string; frames: number } }[] = [
    { id: "c1", who: "agent" },
    { id: "c2", who: "caller", toolAfter: { label: "Checked Sara's free times", detail: "2:30 PM and 4:00 PM tomorrow", frames: 14 } },
    { id: "c3", who: "agent" },
    { id: "c4", who: "caller" },
    { id: "c5", who: "agent" },
    { id: "c6", who: "caller", toolAfter: { label: "Booked the appointment", detail: "Haircut with Sara · tomorrow 2:30 PM", frames: 12 } },
    { id: "c7", who: "agent" },
  ];
  const lines: CallLine[] = [];
  const tools: CallTool[] = [];
  let t = 8; // connect + first frames
  for (const o of order) {
    lines.push({ id: o.id, at: t, frames: vf(o.id), who: o.who, text: clip(o.id).text });
    t += vf(o.id);
    if (o.toolAfter) {
      tools.push({ at: t + 4, done: t + 4 + o.toolAfter.frames, label: o.toolAfter.label, detail: o.toolAfter.detail });
      t += o.toolAfter.frames + 3;
    } else {
      t += 3; // conversational gap
    }
  }
  const last = lines[lines.length - 1];
  tools.push({ at: last.at + 24, done: last.at + 40, label: "Sent a confirmation text", detail: "To Ayesha's phone" });
  return { lines, tools, end: last.at + last.frames + 16 };
}
