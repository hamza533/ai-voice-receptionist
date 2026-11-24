import { expect, test } from "@playwright/test";

import { AGENT_TOKEN, API_URL, E2E_EMAIL, E2E_PASSWORD } from "./fixtures";

/**
 * Main user flow: log in -> change settings -> start a test web call -> see the call record.
 *
 * The call is driven through the same HTTPS endpoints the voice agent uses (service
 * token), which stands in for the audio leg so the test runs in CI without LiveKit or
 * Gemini keys. When LIVEKIT_* keys are configured, the "Talk to receptionist" button
 * also connects for real using Chromium's fake microphone.
 */
test("log in, change greeting, take a call, see it in the dashboard", async ({ page, request }) => {
  const stamp = String(Date.now());
  const greeting = `Thanks for calling Luma Hair Studio, Ava here (${stamp}). How can I help?`;

  // 1. Log in
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_EMAIL);
  await page.getByLabel("Password").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("Calls answered")).toBeVisible();

  // 2. Change settings
  await page.getByRole("link", { name: "Settings" }).first().click();
  await page.getByTestId("greeting").fill(greeting);
  await page.getByTestId("save-settings").click();
  await expect(page.getByText(/Settings saved/)).toBeVisible();

  // 3. Start a test web call from the dashboard
  await page.getByTestId("header-talk").click();
  await page.getByTestId("start-call").click();
  await expect(
    // First visible wins: with live voice keys the call connects and may also warn about the mic.
    page.getByTestId("call-timer").or(page.getByRole("alert")).first(),
  ).toBeVisible();

  // The agent leg: start the call, use tools, end it (exactly what agent/main.py does).
  const auth = { Authorization: `Bearer ${AGENT_TOKEN}` };
  const start = await (await request.post(`${API_URL}/api/agent/calls/start`, {
    headers: auth,
    data: { channel: "web", room_name: "e2e-room", caller_number: "" },
  })).json();
  expect(start.allowed).toBeTruthy();
  // The new setting reaches the next call; the recording notice is inserted before the question.
  expect(start.greeting).toContain(`Ava here (${stamp}).`);
  expect(start.greeting).toContain("This call may be recorded and transcribed. How can I help?");
  const callId = start.call_id as string;

  const avail = await (await request.post(`${API_URL}/api/agent/tools/check_availability`, {
    headers: auth,
    data: { call_id: callId, args: { service: "Haircut", date_from: "tomorrow" } },
  })).json();
  expect(avail.status).toBe("ok");
  const booked = await (await request.post(`${API_URL}/api/agent/tools/book_appointment`, {
    headers: auth,
    data: {
      call_id: callId,
      args: {
        slot_id: avail.data.slots[0].slot_id, service: "Haircut", customer_name: "E2E Tester",
        email: "e2e@example.com", caller_confirmed: true,
      },
    },
  })).json();
  expect(booked.status).toBe("ok");
  const now = new Date();
  await request.post(`${API_URL}/api/agent/calls/${callId}/end`, {
    headers: auth,
    data: {
      ended_at: new Date(now.getTime() + 60_000).toISOString(),
      turns: [
        { speaker: "agent", text: start.greeting, ts: now.toISOString() },
        { speaker: "caller", text: "I'd like a haircut tomorrow please", ts: new Date(now.getTime() + 4000).toISOString() },
      ],
      latency_ms: [640, 710],
    },
  });

  // 4. See the call record (summary is produced by the worker within seconds)
  await page.goto(`/dashboard/calls/${callId}`);
  await expect(page.getByTestId("transcript")).toContainText("I'd like a haircut tomorrow please");
  await expect(page.getByText("Appointment booked").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Haircut").first()).toBeVisible();
});

test("landing page answers a sample question from the FAQ", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Never miss a call again" })).toBeVisible();
  await page.getByRole("button", { name: /Is there parking nearby/ }).click();
  await expect(page.getByText(/street parking/i)).toBeVisible();
});
