import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError, request } from "./api";
import {
  Avatar,
  Dialog,
  ErrorNotice,
  More,
  useList,
  useResource,
  useWrite,
} from "./components";
vi.mock("./api", async (original) => ({
  ...(await original<typeof import("./api")>()),
  request: vi.fn(),
}));
beforeEach(() => {
  vi.mocked(request).mockReset();
});
it("clears old resource data while a different scoped path loads", async () => {
  vi.mocked(request)
    .mockResolvedValueOnce({ name: "Private group" })
    .mockImplementationOnce(() => new Promise(() => {}));
  const hook = renderHook(({ path }) => useResource<{ name: string }>(path), {
    initialProps: { path: "/groups/1" },
  });
  await waitFor(() =>
    expect(hook.result.current.data?.name).toBe("Private group"),
  );
  hook.rerender({ path: "/groups/2" });
  expect(hook.result.current.data).toBeUndefined();
});
it("loads the next page exactly once and resets pagination on refresh", async () => {
  vi.mocked(request).mockImplementation(async (path) => ({
    items: path.includes("offset=0") ? ["A"] : ["B"],
    total: 2,
    offset: 0,
    limit: 50,
  }));
  const hook = renderHook(({ version }) => useList<string>("/users", version), {
    initialProps: { version: 0 },
  });
  await waitFor(() => expect(hook.result.current.items).toEqual(["A"]));
  act(() => hook.result.current.loadMore());
  await waitFor(() => expect(hook.result.current.items).toEqual(["A", "B"]));
  hook.rerender({ version: 1 });
  await waitFor(() => expect(hook.result.current.items).toEqual(["A"]));
  expect(hook.result.current.more).toBe(true);
});
it("retains original key, payload and route for uncertain writes and releases confirmed failures", async () => {
  vi.mocked(request)
    .mockRejectedValueOnce(new ApiError("Unknown outcome", 0, {}, true))
    .mockResolvedValueOnce({ id: 2 })
    .mockRejectedValueOnce(new ApiError("Invalid", 422))
    .mockResolvedValueOnce({ id: 3 });
  const hook = renderHook(useWrite);
  await act(async () => {
    await hook.result.current.send("/groups", { name: "A" }).catch(() => {});
  });
  expect(hook.result.current.uncertain).toBe(true);
  await act(async () => {
    await hook.result.current.send("/users", { name: "B" });
  });
  const calls = vi.mocked(request).mock.calls;
  expect(calls[1]).toEqual(calls[0]);
  await act(async () => {
    await hook.result.current.send("/groups", { name: "C" }).catch(() => {});
  });
  await act(async () => {
    await hook.result.current.send("/groups", { name: "D" });
  });
  expect(calls[3][1]?.key).not.toBe(calls[2][1]?.key);
});
it("uses initial fallback when a portrait fails and displays API field details", () => {
  render(
    <>
      <Avatar person={{ id: 1, name: "Aman", avatar_key: "invalid" }} />
      <ErrorNotice
        error={
          new ApiError("Invalid amount", 422, {
            amount: ["Too precise"],
            name: "Required",
          })
        }
      />
      <More list={{ more: true, loading: true, loadMore: vi.fn() }} />
    </>,
  );
  fireEvent.error(document.querySelector("img")!);
  expect(screen.getByText("A")).toBeVisible();
  expect(screen.getByRole("alert")).toHaveTextContent("amount: Too precise");
  expect(screen.getByRole("button", { name: "Load more" })).toBeDisabled();
});
it("traps forward and backward keyboard focus inside a dialog", () => {
  render(
    <Dialog title="Add person" close={vi.fn()}>
      <input aria-label="Name" />
      <button>Save</button>
    </Dialog>,
  );
  const close = screen.getByRole("button", { name: "Close" });
  const save = screen.getByRole("button", { name: "Save" });
  save.focus();
  fireEvent.keyDown(save, { key: "Tab" });
  expect(close).toHaveFocus();
  close.focus();
  fireEvent.keyDown(close, { key: "Tab", shiftKey: true });
  expect(save).toHaveFocus();
});
