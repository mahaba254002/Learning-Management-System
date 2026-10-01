const API_ORIGIN = "https://learning-management-system-5nws.onrender.com";

export default {
  async fetch(request, env) {
    const requestUrl = new URL(request.url);

    if (requestUrl.pathname.startsWith("/api/")) {
      const apiUrl = new URL(requestUrl.pathname + requestUrl.search, API_ORIGIN);
      return fetch(new Request(apiUrl, request));
    }

    return env.ASSETS.fetch(request);
  },
};