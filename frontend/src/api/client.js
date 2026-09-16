/**
 * Central API client. Every network call in the app should go through
 * apiRequest() rather than calling fetch() directly — this is what
 * guarantees cookies are sent, CSRF headers are attached correctly, and
 * errors have one consistent shape everywhere in the app.
 */

// In production (Vercel), call the Render backend directly since Vercel's
// free plan does not support proxying rewrites to external URLs.
// In local dev, use an empty string so Vite's proxy handles it transparently.
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD
    ? "https://learning-management-system-5nws.onrender.com"
    : "");

const SAFE_METHODS = new Set(["GET", "HEAD"]);

function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

export class ApiError extends Error {
  constructor(status, message, details) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

export async function apiRequest(path, { method = "GET", body } = {}) {
  const headers = {};

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  if (!SAFE_METHODS.has(method)) {
    const csrfToken = getCookie("csrf_token");
    if (csrfToken) {
      headers["X-CSRF-Token"] = csrfToken;
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const data = response.status === 204 ? null : await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      (data && (data.detail || data.message)) ||
      `Request failed with status ${response.status}`;
    throw new ApiError(response.status, typeof message === "string" ? message : "Request failed", data);
  }

  return data;
}