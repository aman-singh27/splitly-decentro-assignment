import { expect, test, type Page } from "@playwright/test";

/** Every test uses Playwright's fresh browser context and a distinct server workspace. */
async function createGroup(page: Page, name = "Dinner with friends") {
  await page.goto("/");
  await page.getByRole("button", { name: "Create group", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Group name").fill(name);
  await dialog
    .getByRole("button", { name: "Create group", exact: true })
    .click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}

async function addPerson(page: Page, name: string) {
  await page.getByRole("button", { name: "Add members", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name", { exact: true }).fill(name);
  await dialog
    .getByRole("button", { name: "Create and add person", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
}

async function prepareDinner(page: Page) {
  await createGroup(page);
  for (const name of ["Mohit", "Rahul", "Ankit"]) await addPerson(page, name);
}

async function recordExpense(page: Page, amount: string, description: string) {
  await page.getByRole("link", { name: /Add expense/ }).click();
  await page
    .getByRole("textbox", { name: "What was it for?", exact: true })
    .fill(description);
  await page.getByLabel("Amount in INR", { exact: true }).fill(amount);
  await page
    .getByRole("combobox", { name: "Paid by", exact: true })
    .selectOption({ label: "Mohit" });
  await page.getByRole("button", { name: "Add expense", exact: true }).click();
  await expect(
    page.getByTestId("expense-row").filter({ hasText: description }),
  ).toBeVisible();
}

test("equal dinner split, saved receipt, explanation, and partial settlement", async ({
  page,
}) => {
  await prepareDinner(page);
  await recordExpense(page, "1200", "Dinner at the cafe");
  await page
    .getByTestId("expense-row")
    .filter({ hasText: "Dinner at the cafe" })
    .locator("summary")
    .first()
    .click();
  await expect(
    page.getByTestId("expense-receipt").getByText("₹400.00", { exact: true }),
  ).toHaveCount(3);
  await page.getByRole("tab", { name: "Balances", exact: true }).click();
  const rahul = page.getByTestId("debt-row").filter({ hasText: "Rahul" });
  const ankit = page.getByTestId("debt-row").filter({ hasText: "Ankit" });
  await expect(rahul).toContainText("Mohit");
  await expect(rahul).toContainText("₹400.00");
  await expect(ankit).toContainText("₹400.00");
  await rahul
    .getByRole("button", { name: "Why this amount?", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Dinner at the cafe");
  await expect(page.getByRole("dialog")).toContainText("₹400.00");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await rahul
    .getByRole("button", { name: "Record payment", exact: true })
    .click();
  const settlement = page.getByRole("dialog");
  await settlement.getByLabel("Amount in INR", { exact: true }).fill("150");
  await settlement
    .getByRole("button", { name: "Record payment", exact: true })
    .click();
  await expect(rahul).toContainText("₹250.00");
  await rahul
    .getByRole("button", { name: "Why this amount?", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("settlement");
  await expect(page.getByRole("dialog")).toContainText("₹250.00");
});

test("adding a late member preserves old participant shares", async ({
  page,
}) => {
  await prepareDinner(page);
  await recordExpense(page, "100.01", "Original dinner");
  await page.getByRole("tab", { name: "Members", exact: true }).click();
  await addPerson(page, "Priya");
  await page.getByRole("tab", { name: "Expenses", exact: true }).click();
  await page
    .getByTestId("expense-row")
    .filter({ hasText: "Original dinner" })
    .locator("summary")
    .first()
    .click();
  const receipt = page.getByTestId("expense-receipt");
  await expect(receipt).toContainText("Mohit");
  await expect(receipt).toContainText("Rahul");
  await expect(receipt).toContainText("Ankit");
  await expect(receipt).not.toContainText("Priya");
  await expect(receipt.getByText("₹33.34", { exact: true })).toHaveCount(2);
  await expect(receipt.getByText("₹33.33", { exact: true })).toHaveCount(1);
});

test("group invite opens in independent browser without other groups or people", async ({
  page,
  browser,
}) => {
  await createGroup(page, "Private household");
  await addPerson(page, "Private person");
  await page.getByRole("link", { name: "Groups", exact: true }).click();
  await createGroup(page, "Shared trip");
  await addPerson(page, "Trip friend");
  await page.getByRole("button", { name: "Share group", exact: true }).click();
  const link = await page.getByTestId("share-url").inputValue();
  const guestContext = await browser.newContext();
  try {
    const guest = await guestContext.newPage();
    await guest.goto(link);
    await expect(
      guest.getByRole("heading", { name: "Shared trip", exact: true }),
    ).toBeVisible();
    await expect(
      guest.getByRole("button", { name: "Create group", exact: true }),
    ).toHaveCount(0);
    await guest.getByRole("link", { name: "People", exact: true }).click();
    await expect(guest.getByText("Trip friend", { exact: true })).toBeVisible();
    await expect(
      guest.getByText("Private person", { exact: true }),
    ).toHaveCount(0);
    await guest.getByRole("link", { name: "Groups", exact: true }).click();
    await expect(
      guest.getByText("Private household", { exact: true }),
    ).toHaveCount(0);
    await expect(
      guest.getByText("Shared trip", { exact: true }).first(),
    ).toBeVisible();
    await guest.getByText("Shared trip", { exact: true }).first().click();
    await guest.getByRole("tab", { name: "Members", exact: true }).click();
    await addPerson(guest, "Guest member");
    await guest.getByRole("link", { name: /Add expense/ }).click();
    await guest
      .getByRole("textbox", { name: "What was it for?", exact: true })
      .fill("Guest contribution");
    await guest.getByLabel("Amount in INR", { exact: true }).fill("100");
    await guest
      .getByRole("combobox", { name: "Paid by", exact: true })
      .selectOption({ label: "Guest member" });
    await guest
      .getByRole("button", { name: "Add expense", exact: true })
      .click();
    await expect(
      guest
        .getByTestId("expense-row")
        .filter({ hasText: "Guest contribution" }),
    ).toBeVisible();
    await guest.getByRole("tab", { name: "Balances", exact: true }).click();
    await expect(guest.getByTestId("debt-row")).toContainText("Trip friend");
    await expect(guest.getByTestId("debt-row")).toContainText("Guest member");
    await expect(guest.getByTestId("debt-row")).toContainText("₹50.00");
  } finally {
    await guestContext.close();
  }
});

test("people directory and empty group explain required member action", async ({
  page,
}) => {
  await createGroup(page, "New group");
  await expect(page.getByText(/add.*member/i).first()).toBeVisible();
  await addPerson(page, "Aman");
  await page.getByRole("link", { name: "People", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "People", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Aman", { exact: true })).toBeVisible();
});

test("invalid money is rejected and form preserves entered description", async ({
  page,
}) => {
  await prepareDinner(page);
  await page.getByRole("link", { name: /Add expense/ }).click();
  await page
    .getByRole("textbox", { name: "What was it for?", exact: true })
    .fill("Keep this draft");
  await page
    .getByRole("combobox", { name: "Paid by", exact: true })
    .selectOption({ label: "Mohit" });
  await page.getByLabel("Amount in INR", { exact: true }).fill("0");
  await page.getByRole("button", { name: "Add expense", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "What was it for?", exact: true }),
  ).toHaveValue("Keep this draft");
  await page.getByLabel("Amount in INR", { exact: true }).fill("12.34");
  await page.getByRole("button", { name: "Add expense", exact: true }).click();
  await expect(
    page.getByTestId("expense-row").filter({ hasText: "Keep this draft" }),
  ).toBeVisible();
  await expect(page.getByText("₹12.34", { exact: true }).first()).toBeVisible();
});

test("API documentation includes working JSON downloads and explorer", async ({
  page,
}) => {
  await page.goto("/developers");
  await expect(
    page.getByRole("heading", { name: /API/i }).first(),
  ).toBeVisible();
  for (const [name, key] of [
    ["OpenAPI", "openapi"],
    ["Postman collection", "info"],
    ["Postman environment", "values"],
  ] as const) {
    const href = await page
      .getByRole("link", { name, exact: true })
      .getAttribute("href");
    expect(href).toBeTruthy();
    const response = await page.request.get(href!);
    expect(response.status()).toBe(200);
    expect(await response.json()).toHaveProperty(key);
  }
  await expect(page.locator(".swagger-ui")).toBeVisible();
});

test("mobile dinner workflow has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await prepareDinner(page);
  await recordExpense(page, "1200", "Mobile dinner");
  await page.getByRole("tab", { name: "Balances", exact: true }).click();
  await expect(page.getByTestId("debt-row")).toHaveCount(2);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/mobile-dinner.png",
    fullPage: true,
  });
});

test("group dialog works with keyboard and restores focus", async ({
  page,
}) => {
  await page.goto("/");
  const create = page.getByRole("button", {
    name: "Create group",
    exact: true,
  });
  await create.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(create).toBeFocused();
});

test("desktop populated group screenshot", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await prepareDinner(page);
  await recordExpense(page, "1200", "Dinner at the cafe");
  await page.getByRole("tab", { name: "Balances", exact: true }).click();
  await expect(page.getByTestId("debt-row")).toHaveCount(2);
  await page.screenshot({
    path: "test-results/desktop-dinner.png",
    fullPage: true,
  });
});

test("custom shares sum exactly and produce the selected member debts", async ({
  page,
}) => {
  await prepareDinner(page);
  await page.getByRole("link", { name: /Add expense/ }).click();
  await page
    .getByRole("textbox", { name: "What was it for?", exact: true })
    .fill("Different orders");
  await page.getByLabel("Amount in INR", { exact: true }).fill("1000");
  await page
    .getByRole("combobox", { name: "Paid by", exact: true })
    .selectOption({ label: "Mohit" });
  await page
    .getByRole("button", { name: "Custom amounts", exact: true })
    .click();
  await page.getByLabel("Share for Mohit", { exact: true }).fill("500");
  await page.getByLabel("Share for Rahul", { exact: true }).fill("300");
  await page.getByLabel("Share for Ankit", { exact: true }).fill("100");
  await page.getByRole("button", { name: "Add expense", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    /sum|total|match|add up/i,
  );
  await expect(
    page.getByRole("textbox", { name: "What was it for?", exact: true }),
  ).toHaveValue("Different orders");
  await page.getByLabel("Share for Ankit", { exact: true }).fill("200");
  await page.getByRole("button", { name: "Add expense", exact: true }).click();
  await expect(
    page.getByTestId("expense-row").filter({ hasText: "Different orders" }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Balances", exact: true }).click();
  await expect(
    page.getByTestId("debt-row").filter({ hasText: "Rahul" }),
  ).toContainText("₹300.00");
  await expect(
    page.getByTestId("debt-row").filter({ hasText: "Ankit" }),
  ).toContainText("₹200.00");
});

// A small real PNG is decoded by the server; the fixture contains no external image data.
const billPhoto = {
  name: "bill.png",
  mimeType: "image/png",
  buffer: Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFUlEQVR4nGP8//8/AzbAhFV00EoAAFbUAw037MyjAAAAAElFTkSuQmCC",
    "base64",
  ),
};

test("optional bill photo can be uploaded and viewed after saving expense", async ({
  page,
}) => {
  await prepareDinner(page);
  await page.getByRole("link", { name: /Add expense/ }).click();
  await page
    .getByRole("textbox", { name: "What was it for?", exact: true })
    .fill("Dinner with photo");
  await page.getByLabel("Amount in INR", { exact: true }).fill("1200");
  await page
    .getByRole("combobox", { name: "Paid by", exact: true })
    .selectOption({ label: "Mohit" });
  await page.getByLabel(/Bill photo \(optional\)/).setInputFiles(billPhoto);
  await page.getByRole("button", { name: "Add expense", exact: true }).click();
  await page
    .getByTestId("expense-row")
    .filter({ hasText: "Dinner with photo" })
    .locator("summary")
    .first()
    .click();
  await page.getByText("View bill photo", { exact: true }).click();
  const image = page.getByRole("img", { name: "Bill photo", exact: true });
  await expect(image).toBeVisible();
  expect(
    await image.evaluate(
      (element) => (element as HTMLImageElement).naturalWidth,
    ),
  ).toBeGreaterThan(0);
});

test("failed photo upload retries attachment without duplicating saved expense", async ({
  page,
}) => {
  await prepareDinner(page);
  let uploads = 0;
  await page.route("**/api/v1/expenses/*/receipt", async (route) => {
    if (route.request().method() === "POST" && ++uploads === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: '{"detail":"Temporary upload failure"}',
      });
    } else await route.continue();
  });
  await page.getByRole("link", { name: /Add expense/ }).click();
  await page
    .getByRole("textbox", { name: "What was it for?", exact: true })
    .fill("Retry photo only");
  await page.getByLabel("Amount in INR", { exact: true }).fill("1200");
  await page
    .getByRole("combobox", { name: "Paid by", exact: true })
    .selectOption({ label: "Mohit" });
  await page.getByLabel(/Bill photo \(optional\)/).setInputFiles(billPhoto);
  await page.getByRole("button", { name: "Add expense", exact: true }).click();
  await expect(page.getByRole("status")).toContainText(
    "Expense saved. Photo upload failed.",
  );
  await page
    .getByRole("button", { name: "Retry photo upload", exact: true })
    .click();
  await expect(
    page.getByTestId("expense-row").filter({ hasText: "Retry photo only" }),
  ).toBeVisible();
  await expect(page.getByTestId("expense-row")).toHaveCount(1);
  expect(uploads).toBe(2);
});

for (const failure of ["network", "invalid-json"] as const) {
  test(`lost expense response (${failure}) freezes the draft and retries the committed record only once`, async ({
    page,
  }) => {
    await prepareDinner(page);
    const keys: string[] = [];
    await page.route("**/api/v1/expenses", async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      keys.push(route.request().headers()["idempotency-key"]);
      if (keys.length === 1) {
        // Commit the genuine server request, then simulate losing its response.
        const committed = await route.fetch();
        expect(committed.status()).toBe(201);
        if (failure === "network") await route.abort("failed");
        else
          await route.fulfill({
            status: 201,
            contentType: "application/json",
            body: '{"id":',
          });
      } else await route.continue();
    });
    await page.getByRole("link", { name: /Add expense/ }).click();
    const description = page.getByRole("textbox", {
      name: "What was it for?",
      exact: true,
    });
    await description.fill("Uncertain network dinner");
    await page.getByLabel("Amount in INR", { exact: true }).fill("1200");
    await page
      .getByRole("combobox", { name: "Paid by", exact: true })
      .selectOption({ label: "Mohit" });
    await page
      .getByRole("button", { name: "Add expense", exact: true })
      .click();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(description).toBeDisabled();
    await page
      .getByRole("button", { name: "Retry same request", exact: true })
      .click();
    await expect(
      page
        .getByTestId("expense-row")
        .filter({ hasText: "Uncertain network dinner" }),
    ).toBeVisible();
    await expect(page.getByTestId("expense-row")).toHaveCount(1);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBe(keys[0]);
  });
}

test("standalone Django API explorer renders with its local assets", async ({
  page,
  baseURL,
}) => {
  // Vite handles the SPA; this separate explorer is served directly by Django.
  const origin = process.env.E2E_BASE_URL ? baseURL! : "http://127.0.0.1:8001";
  const failedAssets: string[] = [];
  page.on("response", (response) => {
    if (response.url().includes("/static/") && response.status() >= 400)
      failedAssets.push(response.url());
  });
  const response = await page.goto(`${origin}/api/docs/`);
  expect(response?.status()).toBe(200);
  await expect(page.locator(".swagger-ui")).toBeVisible();
  await expect(page.locator(".swagger-ui .info .title")).toContainText(
    "Splitly Expense Sharing API",
  );
  await expect(page.locator(".swagger-ui .opblock")).not.toHaveCount(0);
  expect(failedAssets).toEqual([]);
});
