/** Shared rules for what an API error means to the person using Skynet. */

// No connection, or the API is starting up or overloaded (Render sleeps when idle).
export function isTemporary(error) {
  return Boolean(error) && [0, 502, 503, 504].includes(error.status);
}

// Retry temporary failures for about a minute: 2s, 4s, 8s, 15s, 15s, 15s.
export const MAX_RETRIES = 6;
export function retryDelay(attempt) {
  return Math.min(2000 * 2 ** attempt, 15000);
}
export function shouldRetry(failureCount, error) {
  return isTemporary(error) && failureCount < MAX_RETRIES;
}

export function isFeatureOff(error) {
  return error?.status === 403 && /is not enabled for this institution/i.test(error.message || "");
}

/**
 * kind: offline | unavailable | server | session | denied | feature | missing | other
 * saving: true when the failed request was a change, so we can say it may not be saved.
 */
export function describe(error, { saving = false } = {}) {
  const status = error?.status;
  if (status === 0) return { kind: "offline", title: "Can't reach Skynet",
    text: saving ? "Your change may not have been saved. Check your internet connection, then try again." : "Check your internet connection. Skynet keeps trying in the background." };
  if ([502, 503, 504].includes(status)) return { kind: "unavailable", title: "Skynet is starting up",
    text: saving ? "Your change may not have been saved. Wait a moment, then try again." : "This can take up to a minute after a quiet period. Try again shortly." };
  if (status >= 500) return { kind: "server", title: "Something went wrong on our side",
    text: saving ? "Your change was not saved. Try again; if it keeps happening, contact support." : "Try again. If it keeps happening, contact support." };
  if (status === 401) return { kind: "session", title: "Your session has ended", text: "Sign in again to continue." };
  if (isFeatureOff(error)) return { kind: "feature", title: "Not switched on", text: "This feature is not switched on for your institution. Ask your administrator if you need it." };
  if (status === 403) return { kind: "denied", title: saving ? "Not allowed" : "No access",
    text: saving ? (error.message && !/permission to perform/i.test(error.message) ? error.message : "You don't have permission to do this.") : "You don't have access to this. If you think you should, ask your administrator." };
  if (status === 404) return { kind: "missing", title: "Not found", text: "This item was not found, or it is no longer available to you." };
  return { kind: "other", title: "", text: error?.message || "Something went wrong. Try again." };
}
