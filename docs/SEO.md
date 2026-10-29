# Skynet naming and search metadata

The requested public address is https://skynet.mahaba955.workers.dev/. The Cloudflare Worker was renamed from rollback to skynet on 29 October 2026; a branch preview name can still include the Git branch prefix and is not the public production address.

Public metadata lives in frontend/index.html: Skynet title/description, en-KE language, canonical URL, Open Graph/Twitter sharing metadata, public logo, theme colour and SoftwareApplication structured data. No invented ratings, pricing or institution endorsements are included. frontend/public/favicon.svg supplies a Skynet monogram.

frontend/worker.js serves robots.txt and a homepage-only sitemap.xml, adds canonical response metadata and prevents indexing of private HTML, APIs and alternate/preview hosts. API and private HTML responses prohibit shared caching. Robots rules do not replace authentication. The app remains a React SPA; richer public marketing pages and pre-rendering/server rendering are potential improvements. Metadata does not guarantee search ranking or indexing.

Configure PUBLIC_SITE_ORIGIN and INDEX_PUBLIC_SITE for the verified public production origin. Previews use INDEX_PUBLIC_SITE=false and an explicit staging API_ORIGIN. Missing staging configuration returns 503 instead of calling production. Production and preview variables are declared separately in frontend/wrangler.jsonc. Update canonical/social/structured-data URLs together if a custom domain is introduced.

Verify the deployed homepage source and sharing image; request robots.txt/sitemap.xml; check private page and API X-Robots-Tag/Cache-Control headers. frontend/tests/worker-seo.test.js checks routing, request/response preservation, indexing rules and staging isolation. After production verification, submit the public sitemap in your own search console account. Account ownership verification and indexing are external steps, not performed by source changes alone.
