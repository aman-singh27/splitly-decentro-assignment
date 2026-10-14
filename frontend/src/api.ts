export class ApiError extends Error {
  constructor(
    message: string,
    public status = 0,
    public errors: Record<string, string[] | string> = {},
    public uncertain = false,
  ) {
    super(message);
  }
}
export const newKey = () => crypto.randomUUID();
/** Cookies identify scope; CSRF protects writes. A retained key makes uncertain writes retry-safe. */
export async function request<T = any>(
  path: string,
  options: { method?: string; body?: unknown; key?: string } = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const csrf =
    document.cookie
      .split("; ")
      .find((c) => c.startsWith("csrftoken="))
      ?.split("=")[1] ?? "";
  const isForm = options.body instanceof FormData;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined && !isForm)
    headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRFToken"] = decodeURIComponent(csrf);
  if (options.key) headers["Idempotency-Key"] = options.key;
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      headers,
      credentials: "same-origin",
      body:
        options.body === undefined
          ? undefined
          : isForm
            ? (options.body as FormData)
            : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(
      method === "GET"
        ? "Could not connect. Check your connection and retry."
        : "The result is unknown. Retry this same request to safely check whether it saved.",
      0,
      {},
      method !== "GET",
    );
  }
  const data = await response.json().catch(() => {
    // Receiving successful headers does not guarantee the response body arrived.
    // The write may already be committed: retain its key until replay returns
    // the actual record rather than treating an error-shaped fallback as success.
    if (response.ok)
      throw new ApiError(
        method === "GET"
          ? "The server response was incomplete. Retry to load this page."
          : "The result is unknown because the server response was incomplete. Retry this same request to safely recover the saved record.",
        response.status,
        {},
        method !== "GET",
      );
    return {
      detail: "The server could not complete this request. Retry shortly.",
    };
  });
  if (!response.ok)
    throw new ApiError(
      data.detail ?? "Request failed.",
      response.status,
      data.errors ?? {},
      method !== "GET" && response.status >= 500,
    );
  return data;
}
