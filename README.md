# Learning Management System

## Production deployment

The production topology is Netlify for the React SPA, Render for FastAPI and
Redis, and Neon for PostgreSQL. The repository includes [render.yaml](render.yaml)
for the Render Blueprint and [netlify.toml](netlify.toml) for the Netlify build
and `/api/*` proxy.

### Neon

Set these Render environment variables from the same Neon production branch:

- `DATABASE_URL`: pooled connection string for application traffic
- `DATABASE_URL_UNPOOLED`: direct connection string for Alembic and seeding

Also set `JWT_SECRET_KEY`, `ALLOWED_ORIGINS` to the Netlify site URL,
`FRONTEND_BASE_URL` to that same URL, and `ENVIRONMENT=production`. Keep both
database URLs in Render's secret environment settings; never commit them.

### First deployment

Render runs `alembic upgrade head` during its build. After the service is
healthy, run the seed once from a secure shell with the direct Neon URL:

```powershell
cd backend
$env:SEED_DATABASE_URL = "<direct Neon connection string>"
python scripts/seed_demo.py --expected-host <direct Neon host> --apply --password
```

The seed is deterministic, transaction-protected, and non-destructive. It
creates the fictional demo institutions and accounts documented in
[backend/DEMO_DATA.md](backend/DEMO_DATA.md). Do not put the seed password in
Render variables or source control.

### Local verification

```powershell
npm run build --prefix frontend
npm run lint --prefix frontend
$env:PYTHONPATH = "backend"
python -m pytest backend/tests -q
```
