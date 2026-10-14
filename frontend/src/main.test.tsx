import { expect, it, vi } from "vitest";
import { createRoot } from "react-dom/client";
vi.mock("react-dom/client", () => ({
  createRoot: vi.fn(() => ({ render: vi.fn() })),
}));
it("mounts the browser-routed application with locally bundled fonts and styling", async () => {
  document.body.innerHTML = '<div id="root"></div>';
  await import("./main");
  expect(createRoot).toHaveBeenCalledWith(document.getElementById("root"));
  const renderer = vi.mocked(createRoot).mock.results[0].value;
  expect(renderer.render).toHaveBeenCalledOnce();
});
