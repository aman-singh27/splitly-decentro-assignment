import { it, expect, vi, afterEach } from "vitest";
import { request, ApiError } from "./api";
import { act, renderHook } from "@testing-library/react";
import { useWrite } from "./components";
afterEach(() => vi.unstubAllGlobals());
it("sends same-origin credentials, CSRF and retained write key", async () => {
  document.cookie = "csrftoken=test-token";
  const fetch = vi
    .fn()
    .mockResolvedValue(new Response('{"id":1}', { status: 201 }));
  vi.stubGlobal("fetch", fetch);
  await request("/groups", {
    method: "POST",
    body: { name: "Dinner" },
    key: "same-key",
  });
  expect(fetch.mock.calls[0][1]).toMatchObject({
    credentials: "same-origin",
    headers: expect.objectContaining({
      "X-CSRFToken": "test-token",
      "Idempotency-Key": "same-key",
    }),
  });
});
it("surfaces field errors and preserves uncertain network outcomes", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          '{"detail":"Invalid","errors":{"amount":["Too precise"]}}',
          { status: 422 },
        ),
      ),
  );
  await expect(request("/expenses")).rejects.toMatchObject({
    status: 422,
    message: "Invalid",
    errors: { amount: ["Too precise"] },
  });
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  await expect(
    request("/expenses", { method: "POST", body: {} }),
  ).rejects.toMatchObject({ uncertain: true });
});
it("handles non-JSON server failures without masking status", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("gateway", { status: 503 })),
  );
  await expect(request("/groups")).rejects.toBeInstanceOf(ApiError);
});
it("retains an unsafe write key after successful headers but unreadable body", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.reject(new TypeError("Body stream lost")),
    })
    .mockResolvedValueOnce(new Response('{"id":7}', { status: 201 }));
  vi.stubGlobal("fetch", fetch);
  const hook = renderHook(useWrite);
  await act(async () => {
    await hook.result.current
      .send("/groups", { name: "Dinner" })
      .catch(() => {});
  });
  expect(hook.result.current.uncertain).toBe(true);
  await act(async () => {
    expect(
      await hook.result.current.send("/groups", { name: "Edited" }),
    ).toEqual({ id: 7 });
  });
  expect(fetch.mock.calls[1][1].headers["Idempotency-Key"]).toBe(
    fetch.mock.calls[0][1].headers["Idempotency-Key"],
  );
  expect(fetch.mock.calls[1][1].body).toBe(fetch.mock.calls[0][1].body);
});
it("surfaces malformed successful GET bodies as retryable read errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.reject(new SyntaxError("Truncated JSON")),
      }),
  );
  await expect(request("/groups")).rejects.toMatchObject({
    status: 200,
    uncertain: false,
  });
});
