/**
 * Everything the app needs to talk to the HealthVault backend, in one
 * place: the base URL comes from the frontend's own env file (see
 * .env.example), never hardcoded, so pointing this build at a
 * different backend (staging, production) is a config change, not a
 * code change.
 *
 * No screens call this yet — Group A Step 1 is shell + landing page
 * only. This exists now so the pattern is already established for the
 * login/upload/results work that follows.
 */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(message, { status, body } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/**
 * A thin fetch wrapper: resolves paths against API_BASE_URL, sends/
 * expects JSON by default, and turns a non-2xx response into a thrown
 * ApiError carrying the parsed error body (matches the backend's
 * standard error envelope) instead of a generic fetch failure.
 */
export async function apiFetch(path, { method = "GET", body, headers, ...rest } = {}) {
  // FormData (a file upload) must go through untouched - fetch sets its
  // own multipart Content-Type (with the boundary) as long as we don't
  // set one ourselves. Everything else is sent as JSON, as before.
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      Accept: "application/json",
      ...(body !== undefined && !isFormData ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
    ...rest,
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json() : undefined;

  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed (${response.status})`, {
      status: response.status,
      body: data,
    });
  }

  return data;
}

/**
 * Like apiFetch, but for a binary response (e.g. a report page
 * rendered as a PNG) instead of JSON - apiFetch only ever parses JSON
 * or returns undefined, so a real image response needs its own path.
 * Returns a Blob; the caller decides what to do with it (typically
 * URL.createObjectURL for an <img src>).
 */
export async function apiFetchBlob(path, token) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed (${response.status})`, {
      status: response.status,
    });
  }

  return response.blob();
}

export { ApiError };
