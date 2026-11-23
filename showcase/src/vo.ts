// Voiceover timing helpers. src/voiceover.json is written by scripts/voiceover.py.
import manifest from "./voiceover.json";

import { FPS } from "./theme";

export type VoId = keyof typeof manifest;
type Clip = { file: string; seconds: number; text: string; voice: string };

const M = manifest as Record<string, Clip>;

export function clip(id: VoId): Clip {
  return M[id];
}

/** Narration plays slightly faster than recorded (tighter pacing); dialogue stays natural. */
export const NARRATION_RATE = 1.0;

export function rate(id: VoId): number {
  return id.startsWith("n_") ? NARRATION_RATE : 1;
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
    { id: "c2", who: "caller", toolAfter: { label: "Checked availability in Google Calendar", detail: "3 free slots with Sara", frames: 22 } },
    { id: "c3", who: "agent" },
    { id: "c4", who: "caller" },
    { id: "c5", who: "agent" },
    { id: "c6", who: "caller", toolAfter: { label: "Booked the appointment", detail: "Haircut · Sara · 2:30 PM", frames: 20 } },
    { id: "c7", who: "agent" },
  ];
  const lines: CallLine[] = [];
  const tools: CallTool[] = [];
  let t = 14; // connect + first frames
  for (const o of order) {
    lines.push({ id: o.id, at: t, frames: vf(o.id), who: o.who, text: clip(o.id).text });
    t += vf(o.id);
    if (o.toolAfter) {
      tools.push({ at: t + 4, done: t + 4 + o.toolAfter.frames, label: o.toolAfter.label, detail: o.toolAfter.detail });
      t += o.toolAfter.frames + 6;
    } else {
      t += 6; // conversational gap
    }
  }
  const last = lines[lines.length - 1];
  tools.push({ at: last.at + 30, done: last.at + 52, label: "Sent confirmation email", detail: "To ayesha.k@example.com" });
  return { lines, tools, end: last.at + last.frames + 26 };
}
