import { it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { App } from "./App";
import { request } from "./api";
vi.mock("./api", () => ({
  request: vi.fn(),
  ApiError: class extends Error {},
  newKey: () => crypto.randomUUID(),
}));
vi.mock("./Explorer", () => ({
  default: () => <div className="swagger-ui">API explorer</div>,
}));
const person = { id: 1, name: "Mohit", avatar_key: "portrait-01" };
const group = {
  id: 1,
  name: "Dinner",
  member_count: 1,
  expense_count: 0,
  total_expense_minor: 0,
  member_preview: [person],
};
beforeEach(() => {
  vi.mocked(request).mockReset();
  vi.mocked(request).mockImplementation(async (path) => {
    if (path === "/workspace")
      return {
        id: 1,
        scope: "workspace",
        group_id: null,
        can_switch_to_owner: false,
      };
    if (path === "/groups/1") return group;
    if (path.includes("balances"))
      return {
        debts: [],
        members: [
          {
            user_id: 1,
            name: "Mohit",
            avatar_key: "portrait-01",
            net_minor: 0,
            paid_minor: 0,
            allocated_minor: 0,
            owes_minor: 0,
            receivable_minor: 0,
          },
        ],
      };
    return {
      items:
        path.includes("members") || path.includes("users")
          ? [person]
          : path === "/groups"
            ? [group]
            : [],
      total: 1,
    };
  });
});
function mount(route = "/") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  );
}
it("creates a group from the direct groups screen and opens members", async () => {
  mount();
  const u = userEvent.setup();
  await u.click(await screen.findByRole("button", { name: "Create group" }));
  await u.type(screen.getByLabelText("Group name"), "Weekend");
  vi.mocked(request).mockImplementationOnce(async () => ({
    ...group,
    name: "Weekend",
  }));
  await u.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Create group",
    }),
  );
  await waitFor(() =>
    expect(request).toHaveBeenCalledWith(
      "/groups",
      expect.objectContaining({
        body: { name: "Weekend" },
        key: expect.any(String),
      }),
    ),
  );
  expect(
    await screen.findByRole("button", { name: "Add members" }),
  ).toBeVisible();
});
it("closes a keyboard dialog with escape and restores focus", async () => {
  mount();
  const u = userEvent.setup();
  const button = await screen.findByRole("button", { name: "Create group" });
  button.focus();
  await u.keyboard("{Enter}");
  expect(screen.getByRole("dialog")).toBeVisible();
  await u.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(button).toHaveFocus();
});
it("requires valid money and explicit payer, then saves all-member expense", async () => {
  mount("/groups/1/expenses/new");
  const u = userEvent.setup();
  await u.type(await screen.findByLabelText("What was it for?"), "Coffee");
  await u.type(screen.getByLabelText("Amount in INR"), "0");
  await u.click(screen.getByRole("button", { name: "Add expense" }));
  expect(screen.getByRole("alert")).toHaveTextContent("positive");
  await u.clear(screen.getByLabelText("Amount in INR"));
  await u.type(screen.getByLabelText("Amount in INR"), "12.34");
  await u.click(screen.getByRole("button", { name: "Add expense" }));
  await waitFor(() =>
    expect(request).toHaveBeenCalledWith(
      "/expenses",
      expect.objectContaining({
        body: {
          group_id: 1,
          paid_by: 1,
          amount: "12.34",
          description: "Coffee",
        },
      }),
    ),
  );
});
it("exposes scoped people and public API downloads", async () => {
  mount("/people");
  expect(await screen.findByText("Mohit")).toBeVisible();
  expect(screen.getByRole("button", { name: "Add person" })).toBeVisible();
});
it("documents real API with local explorer and exports", async () => {
  mount("/developers");
  expect(
    await screen.findByRole("link", { name: "Postman collection" }),
  ).toHaveAttribute("href", "/api/postman.json");
  expect(await screen.findByText("API explorer")).toBeVisible();
});
it("does not let a group guest create an unrelated group", async () => {
  vi.mocked(request).mockImplementation(async (path) =>
    path === "/workspace"
      ? { id: 1, scope: "group", group_id: 1, can_switch_to_owner: true }
      : { items: [group], total: 1 },
  );
  mount();
  await screen.findByText("Dinner");
  expect(screen.queryByRole("button", { name: "Create group" })).toBeNull();
  expect(
    screen.getByRole("button", { name: "Back to my groups" }),
  ).toBeVisible();
});
