# Deployment and migration process

Use this checklist to upgrade the existing live Skynet installation. Prepared 28 October 2026. Commands below are instructions, not a record of execution. The actual live commit, hosting settings and database revision must be verified first. For architecture, secret inventory and incident handling, see [deployment runbook](DEPLOYMENT.md).

## Release order

**Verify live versions → prepare release → restore/upgrade staging → test → stop production writes → backup → migrate production → deploy API → deploy frontend → smoke-test → reopen → monitor.**

Do not run these steps as one unattended command chain. Stop at any failed check. Keep all services on the same reviewed release commit.

## 1. Prepare the release

At the repository root:

```powershell
git status --short
git diff --stat
git diff --check
```

Review modified and untracked files. Include the new migration files and their matching models/routes. Keep credentials, local `.env` files, dumps and private QA helpers out of Git. Record a reviewed release commit and the current production API/Worker versions in [operations records](OPERATIONS_RECORDS.md).

Before pushing to a hosting-linked branch, inspect automatic deployments. The current Render build command includes `alembic upgrade head`: pushing a change can trigger a database migration before the API release succeeds. Disable automatic deployment during this controlled upgrade if necessary. Confirm the actual service settings rather than assuming render.yaml is already applied.

## 2. Select an isolated staging environment

Use a separate API service, frontend Worker, Redis service/namespace and PostgreSQL staging database/branch. Use a controlled copy of the actual live schema; apply privacy restrictions or synthetic data. Disable real outbound notices on copied data.

Configure secrets privately in the runner/hosting environment:

- DATABASE_URL: runtime connection to the staging database.
- DATABASE_URL_UNPOOLED: direct migration connection to the **same staging database**; must not be empty.
- JWT_SECRET_KEY, REDIS_URL, ENVIRONMENT and frontend origin settings appropriate to staging.

Check both database hosts, branch identifiers and database names privately. Do not print full connection strings. `backend/.env` may point to a hosted database; an arbitrary local command is not automatically isolated. `preview.py` overrides do not apply to ordinary Alembic commands.

The current Cloudflare Worker hard-codes the API origin in `frontend/worker.js`. Staging must use a separately reviewed configuration/entry and Worker name that target staging. Deploying an unchanged copy would call the production API.

## 3. Rehearse the database migration

In a shell using the **release checkout and staging secrets**, from backend:

```powershell
python -m pip install -r requirements-dev.txt
python -m alembic current
python -m alembic heads
python -m alembic history
```

Record the current revision. Verify one intended migration head and inspect every migration between current and head. Source head at this documentation date is `j2f3a4b5c6d7`; always use the command result for a later release.

Then execute, stopping on failure:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

Success means current equals the intended head and schema comparison reports no missing model operations. It does not establish correctness of all data. Check existing accounts, institution settings, enrollments, scores, constraints and counts before/after. Record duration and any lock or duplicate-data failures.

Never use `alembic stamp head` to skip an error. Never run `Base.metadata.create_all` as a substitute for migrations on live data. Upgrade an isolated copy from the actual live revision; an empty-database test alone is insufficient.

Run regression checks from backend:

```powershell
python -m pytest tests -q
```

From frontend:

```powershell
npm ci
npm run lint
node --test tests/*.test.js
npm run build
```

Run the staged four-role/two-institution smoke checks from step 8. Confirm real controlled email delivery independently. Store evidence against the release commit. The previous local feature baseline was 301 backend and 31 frontend tests; do not copy that result as evidence for a different commit.

## 4. Prepare backup and recovery

Arrange an encrypted backup destination outside the running database and retain the backup signing key securely. Test recovery into a separate empty PostgreSQL destination before production migration. Record recovery time, backup timestamp/checksum and acceptable data-loss window.

If using native PostgreSQL tools, configure their own connection variables privately: PGHOST, PGPORT, PGDATABASE, PGUSER and an approved password mechanism. They do not consume SQLAlchemy URLs containing `postgresql+psycopg://`. Confirm the selected database before each tool invocation. Use compatible client/server versions.

Example backup command, from an approved runner with PostgreSQL connection variables already configured and an encrypted destination mounted:

```powershell
pg_dump --format=custom --no-owner --no-privileges --file="VERIFIED_ENCRYPTED_BACKUP_PATH.dump"
```

The path is a placeholder; replace it with the approved location. Check the exit code and record a checksum. A successful dump still requires a restore drill. For recovery, select a **separate empty recovery database** in the PostgreSQL connection settings and explicitly verify its identity before running:

```powershell
pg_restore --exit-on-error --single-transaction --no-owner --no-privileges --dbname="$env:PGDATABASE" "VERIFIED_ENCRYPTED_BACKUP_PATH.dump"
```

Do not run this against the active application database. Confirm required roles/extensions and row counts, then validate the restored application in isolation. Signed institution exports support scoped recovery but are not a substitute for full database recovery.

## 5. Stop writes and migrate production

Confirm the maintenance window, release owner and last good versions. Pause billing jobs and other scheduled writers. Block application writes using an approved edge/hosting maintenance arrangement; this application does not yet have a built-in maintenance switch. Verify traffic cannot continue writing. Take the final recoverable production backup after writes stop.

Use one designated runner with the release checkout and privately configured **production** DATABASE_URL and DATABASE_URL_UNPOOLED. Check the target identity, backup and current revision again. From backend:

```powershell
python -m pip install -r requirements.txt
python -m alembic current
python -m alembic heads
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

Record each result. If any step fails, keep maintenance active, preserve the redacted logs and investigate the failing migration. Do not stamp past it or deploy an API that requires unapplied tables/columns.

## 6. Deploy the matching API

In Render, select the verified existing API service and deploy the reviewed commit. Current repository configuration uses:

```text
Root directory: backend
Build: pip install -r requirements.txt && alembic upgrade head
Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health path: /health
```

After the controlled migration, the build's upgrade should be a no-op. Longer term, separate dependency builds from a designated migration/release stage; that separation is not currently configured by this checklist.

Verify database/Redis connectivity, production HTTPS/cookies, exact allowed frontend origin, Resend sender and backup capabilities. Preserve the existing production JWT secret unless an intentional session reset is required. Check `/health` directly on the API; the current health endpoint only confirms process health, so also exercise authenticated database and Redis-dependent requests.

## 7. Deploy the matching frontend

Build the same release commit in frontend and verify worker.js targets the correct production API and wrangler.jsonc names the intended existing Worker. With an approved Wrangler version installed/configured:

```powershell
npm ci
npm run build
wrangler deploy
```

`wrangler deploy` publishes the Worker and assets. It is not a preview. Wrangler is not currently pinned in package.json; select and record a reviewed CLI version in the release toolchain. Record the deployed Worker version. Keep maintenance active until compatibility checks pass.

## 8. Verify before reopening

Use synthetic test accounts/institutions through the real frontend URL:

- Staff email and learner email/ID login, wrong-role rejection, password change, session refresh/logout.
- Cross-institution access rejection; teacher class scope; read-only delegated workspaces.
- Unfinished-work recovery, reviewed student imports and atomic rejection of a bad batch.
- Attendance, coursework, submission and mark entry; withheld grades private; approved grades/GPA/report values correct.
- Progression advance/repeat/completion, prerequisite/retake rejection, stale approval rejection and preserved records.
- Manual subscription payment and freeze/unfreeze on a test institution; expected support contact.
- Audit action/IP/detail, controlled email delivery, backup capabilities and nested-page reload.
- Mobile layout, keyboard access and visible form errors.

If these pass, resume paused jobs, remove maintenance, confirm a normal user journey and observe errors, latency, database/Redis capacity and email failures. Enable academic rules per pilot institution only after its policies are agreed. Record the release outcome and observation owner.

## 9. Failure and rollback

If frontend/API deployment fails but the migrated schema is compatible with the previous code, redeploy the recorded last good application versions and re-run smoke checks. Reverting application code does not revert the database.

For schema/data failures, prefer a reviewed forward repair. Several academic migrations intentionally refuse downgrades when historical data exists. Do not use a blanket `alembic downgrade` or replace the active database as a routine rollback.

If database recovery is required: keep writes blocked, restore the verified pre-release backup into a separate destination, validate it, assess/reconcile changes after the backup, deliberately switch the API connections, then smoke-test before reopening. Record data loss and recovery actions; retain affected data securely for investigation.

## Completion record

Deployment is complete only after the actual API/Worker versions, final Alembic revision, backup reference, test evidence, resumed jobs, observation results and responsible owner are recorded. See [operations templates](OPERATIONS_RECORDS.md) and [full deployment runbook](DEPLOYMENT.md).
