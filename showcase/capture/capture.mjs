// Captures real screenshots of the running app for the showcase video.
// Run inside the Playwright image on the compose network:
//   BASE=http://web:3000 node capture.mjs /out
import { chromium } from "playwright";

const BASE = process.env.BASE ?? "http://localhost:3010";
const OUT = process.argv[2] ?? "./shots";
const EMAIL = process.env.E2E_EMAIL ?? "owner@luma.example.com";
const PASSWORD = process.env.E2E_PASSWORD ?? "luma-e2e-owner-pass";

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
const shot = async (name, opts = {}) => {
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/${name}.png`, ...opts });
  console.log("captured", name);
};

// Landing
await page.goto(`${BASE}/`);
await page.getByRole("heading", { name: "Never miss a call again" }).waitFor();
await shot("01-landing");
await shot("01-landing-full", { fullPage: true });
await page.getByRole("button", { name: /Is there parking nearby/ }).click();
await page.getByText(/street parking/i).waitFor();
await page.getByText("Try sample questions").scrollIntoViewIfNeeded();
await shot("02-landing-faq");

// Login + overview
await page.goto(`${BASE}/login`);
await shot("03-login");
await page.getByLabel("Email").fill(EMAIL);
await page.getByLabel("Password").fill(PASSWORD);
await page.getByRole("button", { name: "Sign in" }).click();
await page.waitForURL(/\/dashboard$/);
await page.getByText("Calls answered").waitFor();
await page.waitForTimeout(1500);
await shot("04-overview");
await shot("04-overview-full", { fullPage: true });

// Calls
await page.goto(`${BASE}/dashboard/calls`);
await page.getByText("View details").first().waitFor();
await shot("05-calls");

// Booked call detail (a seeded call with a confirmation email)
await page.goto(`${BASE}/dashboard/calls?outcome=booked`);
await page.getByText("View details").first().waitFor();
await page.getByText("View details").first().click();
await page.getByTestId("transcript").waitFor();
await page.waitForTimeout(1200);
await shot("06-call-detail");
await shot("06-call-detail-full", { fullPage: true });

// Appointments: next week, busiest day
await page.goto(`${BASE}/dashboard/appointments`);
await page.getByText("Appointment details").waitFor();
await page.getByRole("button", { name: "Next week" }).click();
await page.waitForTimeout(1200);
let best = { idx: 0, n: -1 };
const days = page.locator("div.grid.grid-cols-7 > button");
for (let i = 0; i < 6; i++) {
  await days.nth(i).click();
  await page.waitForTimeout(400);
  const txt = await page.getByText(/\d+ booked/).first().textContent();
  const n = Number((txt ?? "0").match(/\d+/)?.[0] ?? 0);
  if (n > best.n) best = { idx: i, n };
}
await days.nth(best.idx).click();
await page.waitForTimeout(800);
await shot("07-appointments");

// Messages, knowledge, settings
await page.goto(`${BASE}/dashboard/messages`);
await page.waitForTimeout(1200);
await shot("08-messages");
await page.goto(`${BASE}/dashboard/knowledge`);
await page.getByText("Salon knowledge base").waitFor();
await page.getByPlaceholder("Do you take walk-ins?").fill("Do you take walk-ins?");
await page.getByRole("button", { name: "Ask" }).click();
await page.getByText(/walk-ins when a stylist is free/i).waitFor();
await shot("09-knowledge");
await page.goto(`${BASE}/dashboard/settings`);
await page.getByText("Agent settings & preferences").waitFor();
await shot("10-settings");

// Team & schedules (first person selected), waitlist, setup wizard, notifications
await page.goto(`${BASE}/dashboard/team`);
await page.getByText("Working hours").waitFor();
await page.getByText("Time off & breaks").waitFor();
await page.waitForTimeout(1200);
await shot("12-team");
await shot("12-team-full", { fullPage: true });
await page.goto(`${BASE}/dashboard/waitlist`);
await page.getByTestId("waitlist").getByText("Time held").first().waitFor();
await shot("13-waitlist");
await page.goto(`${BASE}/dashboard/setup`);
await page.getByText("Your business").waitFor();
await shot("14-setup");
await page.goto(`${BASE}/dashboard/settings`);
await page.getByText("Customer notifications & waitlist").scrollIntoViewIfNeeded();
await page.evaluate(() => window.scrollBy(0, -120));
await shot("15-settings-notifications");

// Mobile overview (the Stitch screens were mobile-first)
const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, storageState: await ctx.storageState() });
const m = await mobile.newPage();
await m.goto(`${BASE}/dashboard`);
await m.getByText("Calls answered").waitFor();
await m.waitForTimeout(1500);
await m.screenshot({ path: `${OUT}/11-mobile-overview.png` });
console.log("captured 11-mobile-overview");

await browser.close();
