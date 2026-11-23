// Generates an original, royalty-free background track (public/music.wav):
// warm pad + plucked arpeggio + soft bass and kick, 92 BPM, C major.
// Usage: node scripts/music.mjs <seconds>
import { writeFileSync } from "node:fs";

const SR = 44100;
const seconds = Number(process.argv[2] ?? 84);
const N = Math.floor(SR * seconds);
const L = new Float32Array(N);
const R = new Float32Array(N);
const bpm = 92;
const beat = 60 / bpm;
const bar = beat * 4;

const hz = (m) => 440 * Math.pow(2, (m - 69) / 12);
// midi notes: [bass, ...pad]
const CHORDS = [
  [48, 64, 67, 71, 74], // Cmaj9
  [45, 60, 64, 67, 71], // Am9
  [41, 57, 60, 64, 67], // Fmaj9
  [43, 59, 62, 64, 69], // G6/9
];

function add(buf, i, v) {
  if (i >= 0 && i < N) buf[i] += v;
}

// Pad: each chord lasts 2 bars, smooth attack/release, a few soft harmonics.
const chordLen = bar * 2;
for (let c = 0; c * chordLen < seconds; c++) {
  const chord = CHORDS[c % CHORDS.length];
  const t0 = c * chordLen;
  const start = Math.floor(t0 * SR);
  const len = Math.floor((chordLen + 1.2) * SR);
  for (const [k, note] of chord.slice(1).entries()) {
    const f = hz(note);
    const pan = 0.5 + (k - 1.5) * 0.15;
    for (let i = 0; i < len; i++) {
      const t = i / SR;
      const env = Math.min(1, t / 1.4) * Math.min(1, Math.max(0, (chordLen + 1.2 - t) / 1.2));
      const lfo = 1 + 0.003 * Math.sin(2 * Math.PI * 0.2 * t + k);
      const s =
        Math.sin(2 * Math.PI * f * lfo * t) * 0.6 +
        Math.sin(2 * Math.PI * f * 2.001 * t) * 0.18 +
        Math.sin(2 * Math.PI * f * 0.5 * t) * 0.12;
      const v = s * env * 0.045;
      add(L, start + i, v * (1 - pan) * 2);
      add(R, start + i, v * pan * 2);
    }
  }
  // Bass
  const fb = hz(chord[0]);
  for (let i = 0; i < Math.floor(chordLen * SR); i++) {
    const t = i / SR;
    const env = Math.min(1, t / 0.05) * Math.exp(-t * 0.35);
    const v = Math.sin(2 * Math.PI * fb * t) * env * 0.11;
    add(L, start + i, v);
    add(R, start + i, v);
  }
}

// Arpeggio: 8th notes cycling chord tones an octave up, from bar 2.
const eighth = beat / 2;
for (let n = Math.floor((bar * 2) / eighth); n * eighth < seconds - 4; n++) {
  const t0 = n * eighth;
  const chord = CHORDS[Math.floor(t0 / chordLen) % CHORDS.length];
  const tones = chord.slice(1);
  const pattern = [0, 1, 2, 3, 2, 1, 3, 2];
  const note = tones[pattern[n % pattern.length]] + 12;
  const f = hz(note);
  const start = Math.floor(t0 * SR);
  const pan = n % 2 ? 0.7 : 0.3;
  const accent = n % 4 === 0 ? 1 : 0.7;
  for (let i = 0; i < Math.floor(0.6 * SR); i++) {
    const t = i / SR;
    const env = Math.min(1, t / 0.004) * Math.exp(-t * 7);
    // triangle-ish pluck
    const ph = (f * t) % 1;
    const tri = 1 - 4 * Math.abs(ph - 0.5);
    const v = (tri * 0.6 + Math.sin(2 * Math.PI * f * t) * 0.4) * env * 0.05 * accent;
    add(L, start + i, v * (1 - pan) * 2);
    add(R, start + i, v * pan * 2);
  }
}

// Soft kick on beats 1 and 3 between 8 s and the last 6 s.
for (let b = Math.ceil(8 / beat); b * beat < seconds - 6; b++) {
  if (b % 2) continue;
  const start = Math.floor(b * beat * SR);
  for (let i = 0; i < Math.floor(0.25 * SR); i++) {
    const t = i / SR;
    const f = 50 + 70 * Math.exp(-t * 30);
    const v = Math.sin(2 * Math.PI * f * t) * Math.exp(-t * 14) * 0.16;
    add(L, start + i, v);
    add(R, start + i, v);
  }
}

// Master: fade in/out, gentle saturation, normalise to -3 dBFS.
let peak = 0;
for (let i = 0; i < N; i++) {
  const t = i / SR;
  const fade = Math.min(1, t / 2) * Math.min(1, (seconds - t) / 4);
  L[i] = Math.tanh(L[i] * 1.2) * fade;
  R[i] = Math.tanh(R[i] * 1.2) * fade;
  peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
}
const gain = 0.7 / (peak || 1);
const data = Buffer.alloc(N * 4);
for (let i = 0; i < N; i++) {
  data.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i] * gain)) * 32767), i * 4);
  data.writeInt16LE(Math.round(Math.max(-1, Math.min(1, R[i] * gain)) * 32767), i * 4 + 2);
}
const header = Buffer.alloc(44);
header.write("RIFF", 0);
header.writeUInt32LE(36 + data.length, 4);
header.write("WAVE", 8);
header.write("fmt ", 12);
header.writeUInt32LE(16, 16);
header.writeUInt16LE(1, 20);
header.writeUInt16LE(2, 22);
header.writeUInt32LE(SR, 24);
header.writeUInt32LE(SR * 4, 28);
header.writeUInt16LE(4, 32);
header.writeUInt16LE(16, 34);
header.write("data", 36);
header.writeUInt32LE(data.length, 40);
writeFileSync(new URL("../public/music.wav", import.meta.url), Buffer.concat([header, data]));
console.log(`music.wav: ${seconds}s`);
