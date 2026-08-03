import { expect, test } from "@playwright/test";

test("dashboard loads and exposes operational proof", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /See process drift/i })).toBeVisible();
  await expect(page.getByText("OEE", { exact: true })).toBeVisible();
  await expect(page.getByText("LIVE EVENT STREAM")).toBeVisible();
});

test("pressure drift scenario generates evidence", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Pressure drift" }).click();

  await expect(page.getByText("Pressure drift", { exact: true })).toHaveClass(/active/);
  await expect(page.getByText("Latest production events")).toBeVisible();
});

test("readiness endpoint is directly inspectable", async ({ request }) => {
  const response = await request.get("/ready");
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toMatchObject({ status: "ready" });
});
