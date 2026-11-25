import { expect, type Page, test } from "@playwright/test";

import { E2E_EMAIL, E2E_PASSWORD } from "./fixtures";

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_EMAIL);
  await page.getByLabel("Password").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("owner sets a person's hours and a weekly break on the Team page", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Team" }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Team & schedules" })).toBeVisible();
  await page.getByTestId("team-list").getByText("Omar").click();

  await page.getByRole("button", { name: "Their own hours" }).click();
  await expect(page.getByTestId("shift-editor")).toBeVisible();
  await page.getByTestId("save-shifts").click();
  await expect(page.getByText(/hours saved/)).toBeVisible();

  const note = `Lunch ${Date.now()}`;
  await page.getByLabel("Time off type").click();
  await page.getByRole("option", { name: "Weekly break (e.g. lunch)" }).click();
  await page.getByPlaceholder("Holiday, training, lunch…").fill(note);
  await page.getByTestId("add-time-off").click();
  await expect(page.getByTestId("time-off-list")).toContainText(note);
  await page
    .getByTestId("time-off-list")
    .locator("div", { hasText: note })
    .getByRole("button", { name: "Remove time off" })
    .click();
  await expect(page.getByTestId("time-off-list")).not.toContainText(note);

  // Back to salon hours, so other tests see the default schedule.
  await page.getByRole("button", { name: "Same as salon hours" }).click();
  await page.getByTestId("save-shifts").click();
  await expect(page.getByText(/salon's hours/)).toBeVisible();
});

test("staff add someone to the waitlist and see the new settings", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Waitlist" }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Waitlist" })).toBeVisible();
  await page.getByTestId("waitlist-add-toggle").click();
  const name = `Dana ${Date.now()}`;
  await page.getByLabel("Name").fill(name);
  await page.getByLabel("Mobile number").fill("+92 300 5550101");
  await page.getByLabel("Day", { exact: true }).fill("2030-01-15");
  await page.getByLabel("Service").click();
  await page.getByRole("option", { name: "Haircut", exact: true }).click();
  await page.getByRole("button", { name: "Add to waitlist" }).click();
  await expect(page.getByTestId("waitlist")).toContainText(name);
  await page.getByRole("button", { name: `Remove ${name}` }).click();
  await expect(page.getByTestId("waitlist")).not.toContainText(name);

  await page.goto("/dashboard/settings");
  await expect(page.getByText("Customer notifications & waitlist")).toBeVisible();
  await expect(page.getByText("Holidays & closures")).toBeVisible();
  await expect(page.getByTestId("google-calendar")).toBeVisible();
  await expect(page.getByText("Value booked by Ava")).toHaveCount(0); // only on the overview

  await page.goto("/dashboard");
  await expect(page.getByText("Value booked by Ava")).toBeVisible();
});
