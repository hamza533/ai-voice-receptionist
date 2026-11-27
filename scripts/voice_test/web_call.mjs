// Places a real web call to the running receptionist with recorded audio as the caller.
// Prints the live transcript and the receptionist's tool actions as they arrive.
//
// Fixed recording (Chrome loops the file as the microphone):
//   BASE=http://web:3000 CALLER_WAV=/x/caller.wav node web_call.mjs [seconds] [screenshot.png]
// Interactive caller (one WAV per turn, each played once Ava has finished speaking):
//   CALLER_TURNS=/x/turn1.wav,/x/turn2.wav,... node web_call.mjs [seconds] [screenshot.png]
import fs from "node:fs";
import net from "node:net";
import { chromium } from "playwright";

// getUserMedia only works in a secure context (https or localhost). Inside docker the app
// is at http://web:3000, so expose it on localhost with a tiny TCP proxy (PROXY_TO=web:3000).
if (process.env.PROXY_TO) {
  const [host, port] = process.env.PROXY_TO.split(":");
  net
    .createServer((c) => {
      const s = net.connect(Number(port), host);
      c.pipe(s).pipe(c);
      s.on("error", () => c.destroy());
      c.on("error", () => s.destroy());
    })
    .listen(3010, "127.0.0.1");
}

const BASE = process.env.BASE ?? "http://localhost:3010";
const WAV = process.env.CALLER_WAV;
const TURNS = (process.env.CALLER_TURNS ?? "").split(",").filter(Boolean);
const QUIET_MS = Number(process.env.QUIET_MS ?? 2500); // Ava silent this long = her turn is over
const seconds = Number(process.argv[2] ?? 45);
const shot = process.argv[3];

const browser = await chromium.launch({
  args: [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    ...(WAV && !TURNS.length ? [`--use-file-for-fake-audio-capture=${WAV}`] : []),
    "--autoplay-policy=no-user-gesture-required",
    // getUserMedia needs a secure context; the docker hostname is plain http.
    `--unsafely-treat-insecure-origin-as-secure=${BASE}`,
  ],
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, permissions: ["microphone"] });

if (TURNS.length) {
  // The microphone becomes a Web Audio stream we can speak into on cue with window.__say(i).
  await ctx.addInitScript(() => {
    let ac;
    let dest;
    const ensure = () => {
      if (!ac) {
        ac = new AudioContext({ sampleRate: 48000 });
        dest = ac.createMediaStreamDestination();
        // Faint room noise, like a real microphone: pure digital silence is not sent at all
        // (Opus DTX), so the receptionist would never hear that the caller stopped talking.
        const noise = ac.createBuffer(1, 48000 * 2, 48000);
        const d = noise.getChannelData(0);
        for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * 0.003;
        const room = ac.createBufferSource();
        room.buffer = noise;
        room.loop = true;
        room.connect(dest);
        room.start();
      }
      return dest;
    };
    const real = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async (c) => {
      if (c && c.audio && !c.video) return new MediaStream(ensure().stream.getAudioTracks().map((t) => t.clone()));
      return real(c);
    };
    window.__say = async (i) => {
      ensure();
      await ac.resume();
      const buf = await ac.decodeAudioData(await (await fetch(`/__turns/${i}.wav`)).arrayBuffer());
      const src = ac.createBufferSource();
      src.buffer = buf;
      src.connect(dest);
      await new Promise((r) => {
        src.onended = r;
        src.start();
      });
    };
  });
  await ctx.route("**/__turns/*.wav", (route) => {
    const i = Number(new URL(route.request().url()).pathname.split("/").pop().replace(".wav", ""));
    route.fulfill({ status: 200, contentType: "audio/wav", body: fs.readFileSync(TURNS[i]) });
  });
}

const page = await ctx.newPage();
page.on("console", (m) => {
  if (["error", "warning"].includes(m.type())) console.log(`[browser ${m.type()}]`, m.text().slice(0, 220));
});
await page.goto(`${BASE}/call`);
const t0 = Date.now();
await page.getByTestId("start-call").click();
await page.getByTestId("call-timer").waitFor({ timeout: 30_000 });
const ts = () => `${((Date.now() - t0) / 1000).toFixed(0)}s`;
console.log(`connected in ${ts()}`);

const transcript = page.getByTestId("live-transcript");
const status = async () => (await page.getByTestId("call-timer").locator("..").innerText().catch(() => "")).trim();
const snapshot = async () =>
  transcript.locator(":scope > div").evaluateAll((els) =>
    els.map((e) => ({ ava: e.classList.contains("items-start"), text: e.querySelector("p")?.textContent ?? "" })),
  );

const deadline = Date.now() + seconds * 1000;
let micReported = false;
let next = 0;
let avaHeard = 0; // Ava lines on screen when the caller last spoke
let lastKey = "";
let changedAt = Date.now();
while (Date.now() < deadline) {
  await page.waitForTimeout(500);
  if (!micReported && (await page.getByTestId("mic-off").count())) {
    console.log(`[${ts()}] microphone is OFF in the page`);
    micReported = true;
  }
  const lines = await snapshot();
  const key = JSON.stringify(lines);
  if (key !== lastKey) {
    lastKey = key;
    changedAt = Date.now();
  }
  if (!TURNS.length || next >= TURNS.length) continue;
  // The caller's own words are transcribed a moment late and can land below Ava's reply,
  // so wait for a new Ava line (not "last line is Ava's") and for her to stop talking.
  const avaLines = lines.filter((l) => l.ava).length;
  const avaDone =
    avaLines > avaHeard && !/Speaking|Thinking/.test(await status()) && Date.now() - changedAt >= QUIET_MS;
  if (avaDone) {
    console.log(`[${ts()}] caller says turn ${next + 1}`);
    await page.evaluate((i) => window.__say(i), next);
    next += 1;
    avaHeard = avaLines;
    changedAt = Date.now();
  }
}
console.log("TRANSCRIPT:");
for (const l of await snapshot()) console.log(`  ${l.ava ? "Ava" : "Caller"}: ${l.text}`);
const actions = await page
  .getByText("What the AI is doing")
  .locator("..")
  .innerText({ timeout: 3000 })
  .catch(() => "(call screen not shown)");
console.log("AI actions:", actions.replace(/\n+/g, " | "));
if (shot) await page.screenshot({ path: shot });
await page.getByRole("button", { name: "End call" }).click({ timeout: 3000 }).catch(() => {});
await page.waitForTimeout(3000);
await browser.close();
process.exit(0);
