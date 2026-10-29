export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const site = new URL(env.PUBLIC_SITE_ORIGIN || 'https://skynet.mahaba955.workers.dev');
    const indexable = (env.INDEX_PUBLIC_SITE === true || env.INDEX_PUBLIC_SITE === 'true') && url.origin === site.origin;
    const noindex = { 'X-Robots-Tag': 'noindex, nofollow', 'Cache-Control': 'no-store' };
    if (url.pathname === '/robots.txt') {
      const body = indexable
        ? `User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /platform/\nDisallow: /institution/\nDisallow: /teacher/\nDisallow: /student/\nDisallow: /invite/\nDisallow: /login\nDisallow: /sign-in\nDisallow: /forgot-password\nDisallow: /reset-password\nDisallow: /change-password\nSitemap: ${site.origin}/sitemap.xml\n`
        : 'User-agent: *\nDisallow: /\n';
      return new Response(body, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }
    if (url.pathname === '/sitemap.xml') {
      return new Response(indexable ? `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>${site.origin}/</loc></url></urlset>` : '', {
        status: indexable ? 200 : 404, headers: { 'Content-Type': 'application/xml; charset=utf-8', ...(!indexable ? noindex : {}) },
      });
    }
    if (url.pathname.startsWith('/api/')) {
      // Previews require an explicit staging API; never fall back to production.
      if (!env.API_ORIGIN) return Response.json({ detail: 'The staging API has not been configured.' }, { status: 503, headers: noindex });
      const api = new URL(env.API_ORIGIN);
      if (api.protocol !== 'https:' || api.username || api.password || api.pathname !== '/' || api.search || api.hash) {
        return Response.json({ detail: 'API configuration is invalid.' }, { status: 503, headers: noindex });
      }
      const upstream = await fetch(new Request(new URL(url.pathname + url.search, api), request));
      const response = new Response(upstream.body, upstream);
      Object.entries(noindex).forEach(([key, value]) => response.headers.set(key, value));
      return response;
    }
    const asset = await env.ASSETS.fetch(request);
    const response = new Response(asset.body, asset);
    if (!indexable || url.pathname !== '/') {
      response.headers.set('X-Robots-Tag', 'noindex, nofollow');
    } else response.headers.set('Link', `<${site.origin}/>; rel="canonical"`);
    if (!['GET', 'HEAD'].includes(request.method) || response.headers.get('Content-Type')?.includes('text/html') && url.pathname !== '/') response.headers.set('Cache-Control', 'no-store');
    return response;
  },
};
