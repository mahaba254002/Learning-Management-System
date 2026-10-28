/**
 * Central API client. Every network call in the app should go through
 * apiRequest() rather than calling fetch() directly — this is what
 * guarantees cookies are sent, CSRF headers are attached correctly, and
 * errors have one consistent shape everywhere in the app.
 */

// Empty string → relative paths → proxied by Vercel (production) or
// Vite dev server (local). Keeps everything same-origin so SameSite cookies
// and CSRF (document.cookie) work correctly in all browsers.
const API_BASE_URL = "";

const SAFE_METHODS = new Set(["GET", "HEAD"]);
let workspaceAccess = null;
let refreshInFlight = null;

async function renewSession() {
  if (!refreshInFlight) {
    const previousCsrf = getCookie('csrf_token');
    const renew = async () => {
      if (!previousCsrf) throw new ApiError(401, 'Please sign in to continue.');
      // Another tab may already have rotated the cookies while this tab waited.
      if (previousCsrf && previousCsrf !== getCookie('csrf_token')) return;
      const response = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'include',
        headers: { 'X-CSRF-Token': getCookie('csrf_token') || '' } });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new ApiError(response.status, data?.detail || 'Unable to renew your session.');
      }
    };
    refreshInFlight = (typeof navigator !== 'undefined' && navigator.locks
      ? navigator.locks.request('skynet-session-refresh', renew) : renew()).finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

export function setWorkspaceAccess(access) {
  workspaceAccess = access;
}

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

export async function apiRequest(path, { method = "GET", body, rawBody, responseType = "json", extraHeaders = {}, workspace = true, retrySession = true } = {}) {
  const headers = { ...extraHeaders };
  if (workspace && workspaceAccess) {
    const management = ["/api/workspace-access/start", "/api/workspace-access/stop"].includes(path);
    if (workspaceAccess.read_only && !SAFE_METHODS.has(method) && !management) {
      throw new ApiError(403, "This workspace is read-only. Changes are not permitted.");
    }
    headers["X-Workspace-Token"] = workspaceAccess.token;
  }

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (rawBody !== undefined) headers["Content-Type"] = "application/octet-stream";

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
    body: rawBody !== undefined ? rawBody : body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 401 && retrySession && !path.startsWith('/api/auth/')) {
    try {
      await renewSession();
    } catch (error) {
      if (error.status === 401 && typeof window !== 'undefined') window.dispatchEvent(new Event('skynet:session-ended'));
      throw error;
    }
    return apiRequest(path, { method, body, rawBody, responseType, extraHeaders, workspace, retrySession: false });
  }

  if (response.ok && responseType === "blob") return response.blob();
  const data = response.status === 204 ? null : await response.json().catch(() => null);

  if (response.status === 403 && data?.detail === 'CSRF token missing or invalid' && retrySession && !path.startsWith('/api/auth/')) {
    const currentCsrf = getCookie('csrf_token');
    // A different tab can rotate CSRF after this request's headers were built.
    // CSRF rejection occurs before a mutation runs, so one fresh-header retry is safe.
    if (currentCsrf && currentCsrf !== headers['X-CSRF-Token']) {
      return apiRequest(path, { method, body, rawBody, responseType, extraHeaders, workspace, retrySession: false });
    }
    if (!currentCsrf && typeof window !== 'undefined') window.dispatchEvent(new Event('skynet:session-ended'));
  }

  if (!response.ok) {
    const message =
      (data && (data.detail || data.message)) ||
      `Request failed with status ${response.status}`;
    const validation = Array.isArray(message) ? message.map(issue => `${issue.loc?.filter(part => part !== 'body').join(' · ') || 'Input'}: ${issue.msg}`).join('; ') : null;
    throw new ApiError(response.status, typeof message === "string" ? message : validation || "Request failed", data);
  }

  return data;
}
