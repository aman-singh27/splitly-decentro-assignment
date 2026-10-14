import { beforeEach, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { App } from "./App";
import { request, ApiError } from "./api";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  request: vi.fn(),
}));
vi.mock("./Explorer", () => ({ default: () => <div>API explorer</div> }));
const people = [
  { id: 1, name: "Mohit", avatar_key: "portrait-01" },
  { id: 2, name: "Rahul", avatar_key: "portrait-02" },
];
const group = {
  id: 1,
  name: "Dinner",
  member_count: 2,
  expense_count: 1,
  total_expense_minor: 10000,
  member_preview: people,
};
const expense = {
  id: 7,
  group_id: 1,
  description: "Dinner bill",
  paid_by: people[0],
  amount_minor: 10000,
  participant_count: 2,
  created_at: "2026-10-14T10:00:00Z",
  shares: people.map((p) => ({
    user_id: p.id,
    name: p.name,
    avatar_key: p.avatar_key,
    amount_minor: 5000,
  })),
};
const balances = {
  debts: [
    { from_user_id: 2, to_user_id: 1, amount_minor: 5000, amount: "50.00" },
  ],
  members: people.map((p, i) => ({
    user_id: p.id,
    name: p.name,
    avatar_key: p.avatar_key,
    paid_minor: i ? 0 : 10000,
    allocated_minor: 5000,
    owes_minor: i ? 5000 : 0,
    receivable_minor: i ? 0 : 5000,
    net_minor: i ? -5000 : 5000,
  })),
};
function page(items: unknown[]) {
  return { items, total: items.length, limit: 50, offset: 0 };
}
let custom: ((path: string, options: any) => any) | undefined;
beforeEach(() => {
  custom = undefined;
  vi.mocked(request).mockReset();
  vi.mocked(request).mockImplementation(async (path, options) => {
    const intercepted = custom?.(path, options);
    if (intercepted !== undefined) return intercepted;
    if (path === "/workspace")
      return {
        id: 1,
        scope: "workspace",
        group_id: null,
        can_switch_to_owner: false,
      };
    if (path === "/groups/1") return group;
    if (path.startsWith("/groups/1/members?") || path.startsWith("/users?"))
      return page(people);
    if (path.startsWith("/groups?")) return page([group]);
    if (path.startsWith("/groups/1/expenses?")) return page([expense]);
    if (path === "/groups/1/balances") return balances;
    if (path.includes("/explanation?"))
      return {
        amount_minor: 5000,
        total: 2,
        items: [
          {
            type: "expense",
            record_id: 7,
            description: "Dinner bill",
            created_at: expense.created_at,
            contribution_minor: 6000,
          },
          {
            type: "settlement",
            record_id: 9,
            description: "",
            created_at: expense.created_at,
            contribution_minor: -1000,
          },
        ],
      };
    if (path === "/expenses") return expense;
    if (path.endsWith("/invite")) return { url: "/join#key=grp_test&group=1" };
    if (path === "/users")
      return {
        id: 3,
        name: options?.body && (options.body as any).name,
        avatar_key: "portrait-03",
      };
    return {};
  });
  vi.stubGlobal(
    "URL",
    Object.assign(URL, {
      createObjectURL: vi.fn(() => "blob:photo"),
      revokeObjectURL: vi.fn(),
    }),
  );
});
function mount(route = "/") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  );
}
async function fillExpense() {
  const u = userEvent.setup();
  await u.type(await screen.findByLabelText("What was it for?"), "Coffee");
  await u.type(screen.getByLabelText("Amount in INR"), "10");
  await u.selectOptions(screen.getByLabelText("Paid by"), "1");
  return u;
}

it("shows actual group totals, saved equal shares and optional protected bill photo", async () => {
  custom = (path) =>
    path.startsWith("/groups/1/expenses?")
      ? page([{ ...expense, receipt_url: "/api/v1/expenses/7/receipt" }])
      : undefined;
  mount();
  const u = userEvent.setup();
  await u.click(await screen.findByRole("link", { name: /Dinner/ }));
  await u.click(await screen.findByText("Dinner bill"));
  expect(screen.getByTestId("expense-receipt")).toHaveTextContent(
    "Equal split",
  );
  await u.click(screen.getByText("View bill photo"));
  expect(screen.getByAltText("Bill photo")).toHaveAttribute(
    "src",
    "/api/v1/expenses/7/receipt",
  );
});
it("validates custom allocation and saves exact amounts including zero", async () => {
  mount("/groups/1/expenses/new");
  const u = await fillExpense();
  await u.click(screen.getByRole("button", { name: "Custom amounts" }));
  await u.type(screen.getByLabelText("Share for Mohit"), "9");
  await u.type(screen.getByLabelText("Share for Rahul"), "0");
  await u.click(screen.getByRole("button", { name: "Add expense" }));
  expect(screen.getByRole("alert")).toHaveTextContent("exactly");
  await u.clear(screen.getByLabelText("Share for Mohit"));
  await u.type(screen.getByLabelText("Share for Mohit"), "10");
  await u.click(screen.getByRole("button", { name: "Add expense" }));
  await waitFor(() =>
    expect(request).toHaveBeenCalledWith(
      "/expenses",
      expect.objectContaining({
        body: {
          group_id: 1,
          paid_by: 1,
          amount: "10",
          description: "Coffee",
          split_type: "custom",
          splits: [
            { user_id: 1, amount: "10" },
            { user_id: 2, amount: "0" },
          ],
        },
      }),
    ),
  );
});
it("retries only the optional photo after saving expense, without duplicating expense", async () => {
  let uploads = 0;
  custom = (path) =>
    path.endsWith("/receipt")
      ? ++uploads === 1
        ? Promise.reject(new ApiError("Photo unavailable", 503, {}, true))
        : {}
      : undefined;
  mount("/groups/1/expenses/new");
  const u = await fillExpense();
  await u.upload(
    screen.getByLabelText(/Bill photo/),
    new File(["image"], "receipt.png", { type: "image/png" }),
  );
  expect(screen.getByAltText("Selected bill photo")).toBeVisible();
  await u.click(screen.getByRole("button", { name: "Add expense" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Expense saved");
  expect(screen.getByLabelText("Amount in INR")).toBeDisabled();
  await u.click(screen.getByRole("button", { name: "Retry photo upload" }));
  await screen.findByText("Expense history");
  expect(
    vi.mocked(request).mock.calls.filter(([path]) => path === "/expenses"),
  ).toHaveLength(1);
  const calls = vi
    .mocked(request)
    .mock.calls.filter(([path]) => path.endsWith("/receipt"));
  expect(calls).toHaveLength(2);
  expect(calls[0][1]?.key).toBe(calls[1][1]?.key);
  expect(calls[0][1]?.body).toBe(calls[1][1]?.body);
});
it("continues without a photo when attachment fails and rejects unsupported photos", async () => {
  custom = (path) =>
    path.endsWith("/receipt")
      ? Promise.reject(new ApiError("Invalid photo", 422))
      : undefined;
  mount("/groups/1/expenses/new");
  const u = await fillExpense();
  await userEvent
    .setup({ applyAccept: false })
    .upload(
      screen.getByLabelText(/Bill photo/),
      new File(["x"], "bill.svg", { type: "image/svg+xml" }),
    );
  expect(screen.getByRole("alert")).toHaveTextContent("JPEG");
  await u.upload(
    screen.getByLabelText(/Bill photo/),
    new File(["image"], "receipt.png", { type: "image/png" }),
  );
  await u.click(screen.getByRole("button", { name: "Add expense" }));
  await u.click(
    await screen.findByRole("button", { name: "Continue without photo" }),
  );
  expect(await screen.findByText("Expense history")).toBeVisible();
});
it("explains positive and negative contributions and records a partial outside payment", async () => {
  mount("/groups/1?tab=balances");
  const u = userEvent.setup();
  await u.click(
    (
      await screen.findAllByRole("button", {
        name: "Why this amount?",
      })
    )[0],
  );
  expect(await screen.findByText("Recorded payment")).toBeVisible();
  expect(screen.getByRole("dialog")).toHaveTextContent("Dinner bill");
  await u.click(
    within(screen.getByRole("dialog")).getByRole("button", { name: "Close" }),
  );
  await u.click(screen.getByRole("button", { name: "Record payment" }));
  await u.clear(screen.getByLabelText("Amount in INR"));
  await u.type(screen.getByLabelText("Amount in INR"), "51");
  await u.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Record payment",
    }),
  );
  expect(screen.getByRole("alert")).toHaveTextContent("no greater");
  await u.clear(screen.getByLabelText("Amount in INR"));
  await u.type(screen.getByLabelText("Amount in INR"), "25");
  await u.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Record payment",
    }),
  );
  await waitFor(() =>
    expect(request).toHaveBeenCalledWith(
      "/settlements",
      expect.objectContaining({
        body: { group_id: 1, from_user_id: 2, to_user_id: 1, amount: "25" },
      }),
    ),
  );
});
it("allows pair lookup after debts are fully settled", async () => {
  custom = (path) =>
    path === "/groups/1/balances"
      ? { ...balances, debts: [] }
      : path.includes("/explanation?")
        ? { amount_minor: 0, total: 0, items: [] }
        : undefined;
  mount("/groups/1?tab=balances");
  const u = userEvent.setup();
  expect(await screen.findByText("All square.")).toBeVisible();
  await u.selectOptions(screen.getByLabelText("First person"), "1");
  await u.selectOptions(screen.getByLabelText("Second person"), "2");
  await u.click(screen.getByRole("button", { name: "Why this amount?" }));
  expect(
    await screen.findByText("No contributions between these people yet."),
  ).toBeVisible();
});
it("creates people independently, then adds existing people through the group member dialog", async () => {
  mount("/people");
  const u = userEvent.setup();
  await u.click(await screen.findByRole("button", { name: "Add person" }));
  await u.type(screen.getByLabelText("Name"), "Ankit");
  await u.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Add person",
    }),
  );
  await waitFor(() =>
    expect(request).toHaveBeenCalledWith(
      "/users",
      expect.objectContaining({ body: { name: "Ankit" } }),
    ),
  );
  await u.click(screen.getByRole("link", { name: "Groups" }));
  await u.click(await screen.findByRole("link", { name: /Dinner/ }));
  await u.click(screen.getByRole("tab", { name: "Members" }));
  await u.click(screen.getByRole("button", { name: "Add members" }));
  expect(screen.getAllByText("Already a member")).toHaveLength(2);
  await u.type(screen.getByLabelText("Name"), "Ankit");
  await u.click(screen.getByRole("button", { name: "Create and add person" }));
  await waitFor(() =>
    expect(request).toHaveBeenCalledWith(
      "/groups/1/members",
      expect.objectContaining({ body: { user_id: 3 } }),
    ),
  );
});
it("shares only the selected group and copies its capability link", async () => {
  mount("/groups/1");
  const u = userEvent.setup();
  await u.click(await screen.findByRole("button", { name: "Share group" }));
  const clipboard = vi
    .spyOn(navigator.clipboard, "writeText")
    .mockResolvedValue();
  await u.click(await screen.findByRole("button", { name: "Copy link" }));
  expect(clipboard).toHaveBeenCalledWith(
    expect.stringContaining("/join#key=grp_test&group=1"),
  );
  expect(screen.getByRole("button", { name: "Link copied" })).toBeVisible();
});
it("retries the original existing member after an uncertain add and freezes other actions", async () => {
  let adds = 0;
  const ankit = { id: 3, name: "Ankit", avatar_key: "portrait-03" };
  custom = (path, options) =>
    path.startsWith("/groups/1/members?")
      ? page([people[0]])
      : path.startsWith("/users?")
        ? page([...people, ankit])
        : path === "/groups/1/members" && options?.method === "POST"
          ? ++adds === 1
            ? Promise.reject(
                new ApiError("Unknown membership outcome", 0, {}, true),
              )
            : people[1]
          : undefined;
  mount("/groups/1?tab=members");
  const u = userEvent.setup();
  await u.click(await screen.findByRole("button", { name: "Add members" }));
  await u.click(await screen.findByRole("button", { name: "Add Rahul" }));
  expect(
    await screen.findByRole("button", { name: "Retry adding Rahul" }),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: "Add Ankit" })).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Create and add person" }),
  ).toBeDisabled();
  expect(screen.getByLabelText("Name")).toBeDisabled();
  await u.click(screen.getByRole("button", { name: "Retry adding Rahul" }));
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  const calls = vi
    .mocked(request)
    .mock.calls.filter(([path]) => path === "/groups/1/members");
  expect(calls).toHaveLength(2);
  expect(calls[1]).toEqual(calls[0]);
});
it("joins a group link, rejects incomplete links and restores retained owner workspace", async () => {
  custom = (path) =>
    path === "/workspace"
      ? { id: 1, scope: "group", group_id: 1, can_switch_to_owner: true }
      : path === "/workspace/join"
        ? { id: 1, scope: "group", group_id: 1, can_switch_to_owner: true }
        : path === "/workspace/switch"
          ? {
              id: 1,
              scope: "workspace",
              group_id: null,
              can_switch_to_owner: false,
            }
          : undefined;
  mount("/join#key=grp_test");
  const u = userEvent.setup();
  await u.click(
    await screen.findByRole("button", { name: "Back to my groups" }),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "Back to my groups" }),
    ).not.toBeInTheDocument(),
  );
  await u.click(screen.getByRole("link", { name: "Groups" }));
  expect(
    await screen.findByRole("button", { name: "Create group" }),
  ).toBeVisible();
  await waitFor(() =>
    expect(request).toHaveBeenCalledWith(
      "/workspace/join",
      expect.objectContaining({ body: { access_key: "grp_test" } }),
    ),
  );
});
it("handles incomplete links without making an unsafe join request", async () => {
  mount("/join");
  expect(await screen.findByRole("alert")).toHaveTextContent("incomplete");
  expect(request).not.toHaveBeenCalled();
});
it("shows a failed owner-scope switch while retaining the shared group", async () => {
  custom = (path) =>
    path === "/workspace"
      ? { id: 1, scope: "group", group_id: 1, can_switch_to_owner: true }
      : path === "/workspace/switch"
        ? Promise.reject(new ApiError("Could not restore your groups", 503))
        : undefined;
  mount("/groups/1");
  const u = userEvent.setup();
  await u.click(
    await screen.findByRole("button", { name: "Back to my groups" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not restore",
  );
  expect(
    screen.getByRole("heading", { name: "Dinner", level: 1 }),
  ).toBeVisible();
});
it("shows missing groups and unknown routes with a clear return action", async () => {
  custom = (path) =>
    path === "/groups/1"
      ? Promise.reject(new ApiError("Group not found", 404))
      : undefined;
  mount("/groups/1");
  expect(await screen.findByRole("alert")).toHaveTextContent("Group not found");
  expect(screen.getByRole("link", { name: "Back to Groups" })).toBeVisible();
});
it("initialises a new anonymous workspace after first-visit 401", async () => {
  custom = (path, options) =>
    path === "/workspace"
      ? options?.method === "POST"
        ? {
            id: 1,
            scope: "workspace",
            group_id: null,
            can_switch_to_owner: false,
          }
        : Promise.reject(new ApiError("New session", 401))
      : undefined;
  mount();
  expect(
    await screen.findByRole("button", { name: "Create group" }),
  ).toBeVisible();
  expect(request).toHaveBeenCalledWith(
    "/workspace",
    expect.objectContaining({ method: "POST" }),
  );
});
it("blocks saving while refreshed membership is still loading", async () => {
  mount("/groups/1/expenses/new");
  await fillExpense();
  custom = (path) =>
    path.includes("/members?") ? new Promise(() => {}) : undefined;
  fireEvent(window, new Event("focus"));
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "Add expense" }),
    ).not.toBeInTheDocument(),
  );
  expect(screen.getByRole("status")).toHaveTextContent("Loading members");
});
