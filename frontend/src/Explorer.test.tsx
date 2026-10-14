import { render } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import SwaggerUI from "swagger-ui-dist/swagger-ui-bundle.js";
import Explorer from "./Explorer";
vi.mock("swagger-ui-dist/swagger-ui-bundle.js", () => ({
  default: vi.fn(() => ({ getSystem: () => ({ fn: { clear: vi.fn() } }) })),
}));
it("bundles the API explorer locally, disables remote validation and adds scoped CSRF to requests", () => {
  document.cookie = "csrftoken=explorer%2Dcsrf";
  const { unmount } = render(<Explorer />);
  const config = vi.mocked(SwaggerUI).mock.calls[0][0];
  expect(config.url).toBe("/api/openapi.json");
  expect(config.validatorUrl).toBeNull();
  const request = { headers: {}, credentials: "" };
  expect(config.requestInterceptor(request)).toMatchObject({
    headers: { "X-CSRFToken": "explorer-csrf" },
    credentials: "same-origin",
  });
  unmount();
});
