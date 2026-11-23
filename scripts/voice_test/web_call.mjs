// Places a real web call to the running receptionist with a WAV file as the microphone.
// Prints the live transcript and the receptionist's tool actions as they arrive.
//   BASE=http://web:3000 CALLER_WAV=/x/caller.wav node web_call.mjs [seconds] [screenshot.png]
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
const seconds = Number(process.argv[2] ?? 45);
const shot = process.argv[3];

const browser = await chromium.launch({
  args: [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    ...(WAV ? [`--use-file-for-fake-audio-capture=${WAV}`] : []),
    "--autoplay-policy=no-user-gesture-required",
    // getUserMedia needs a secure context; the docker hostname is plain http.
    `--unsafely-treat-insecure-origin-as-secure=${BASE}`,
  ],
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, permissions: ["microphone"] });
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

const seen = new Set();
const deadline = Date.now() + seconds * 1000;
let micReported = false;
while (Date.now() < deadline) {
  await page.waitForTimeout(1500);
  if (!micReported && (await page.getByTestId("mic-off").count())) {
    console.log(`[${ts()}] microphone is OFF in the page`);
    micReported = true;
  }
  const bubbles = await page.getByTestId("live-transcript").locator("p").allInnerTexts();
  bubbles.forEach((b, i) => {
    const key = `${i}:${b}`;
    if (b.trim() && !seen.has(key) && !seen.has(`${i}:final`)) {
      seen.add(key);
    }
  });
}
const bubbles = await page.getByTestId("live-transcript").locator("div > p").allInnerTexts();
console.log("TRANSCRIPT:");
for (const b of bubbles) console.log("  -", b);
const actions = await page.getByText("What the AI is doing").locator("..").innerText({ timeout: 3000 }).catch(() => "(call screen not shown)");
console.log("AI actions:", actions.replace(/\n+/g, " | "));
if (shot) await page.screenshot({ path: shot });
await page.getByRole("button", { name: "End call" }).click({ timeout: 3000 }).catch(() => {});
await page.waitForTimeout(3000);
await browser.close();
process.exit(0);
