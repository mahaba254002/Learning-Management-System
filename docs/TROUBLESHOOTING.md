# Troubleshooting and repair

Start at [MAINTENANCE.md](MAINTENANCE.md). Use [CODE_MAP.md](CODE_MAP.md) and [ROUTE_REFERENCE.md](ROUTE_REFERENCE.md) to locate the page and handler.

## Collect useful evidence

Record local vs live, time in Africa/Nairobi, page URL, role, institution reference, steps, expected/actual behaviour, failed request method/path/status, redacted response, browser console and matching server log. Never copy authentication cookies, authorization headers, passwords, tokens or identifiable student data. Preserve draft work before reloading. Save the deployed commit and database revision in an incident record.

## Diagnose by symptom

| Symptom | First checks and likely repair location | Verify after repair |
| --- | --- | --- |
| Request failed / 502 / 504 | Browser Network: did `/api` reach the API? Check Worker `frontend/worker.js`, Render startup/deploy logs and API origin. Locally confirm API on 8010 and Vite on 5174; 8000 belongs to another project. | API `/health`, then real login through frontend proxy; health alone does not check DB/Redis/email. |
| Blank page or broken deep link | Console import errors, deployed assets and Worker SPA fallback in `wrangler.jsonc`; route declaration in App.jsx. | Reload a nested URL directly and test mobile. |
| Login returns 401 | Correct portal and assigned identity; staff email, learner email or globally unique ID; account status/password. See auth.py/security.py and both login components. Do not print password hashes or disable checks. | Correct role succeeds; wrong role/password still fails. |
| Session repeatedly expires | `/auth/refresh` response, cookie HTTPS/domain, shared proxy origin, session revocation/absolute lifetime; AuthContext.jsx/client.js/auth.py/pilot.py. Keep JWT signing secret stable across API instances. | Expired access renews once; revoked refresh requires sign-in; unfinished work survives. |
| 403 / CSRF / read-only | Inspect origin, CSRF cookie/header, account role and workspace delegation. See csrf.py, deps.py, workspace_access.py and client.js. | Allowed actor succeeds; unauthorized/read-only actor remains blocked. |
| 404 on a record | Verify tenant, assigned teacher/class, learner enrollment and individual course registration. Tenant hiding can intentionally return 404. | Owner can read; another institution cannot. |
| 409 changed records / stale preview | Concurrent changes or outdated policy/results. Reload server data, review again and resubmit; do not remove expected version/digest checks. | Stale writes rejected, reviewed fresh write succeeds. |
| 422 validation | Read response field names; compare submitted body with route Input schema. Common: missing ID/email, invalid weights, mismatched programme/level, duplicate prerequisites. | Valid request succeeds; invalid input remains rejected. |
| 429 | Rate limit reached. Respect response retry guidance; inspect shared Redis IP buckets. See rate_limit.py. | Retry after window; limits still protect all login portals. |
| 503 sensitive endpoints | Redis unavailable or email/backup service not configured. Inspect server logs and hosting secrets. | Redis and real configured service work; failed delivery is not reported as success. |
| 500 missing table/column | Compare deployed code commit, Alembic current/heads and selected database branch. See models and migration chain. | Rehearse missing migration on isolated PostgreSQL; migrate only through release procedure. |
| Scores/GPA/credits not visible | Assessment published? Grades released? Current approved ALL final grade? Catalogue/credits set? GPA enabled and compatible scheme? Exemptions and period grades differ. See final_grades.py/grading_rules.py/curriculum.py. | Teacher approval permissions, student privacy, report snapshot and stale-mark behaviour. |
| Progression blocked | Read structural issues vs academic thresholds. Source/destination years, programme/levels, prerequisites, released outcomes, attempt limits and existing decision. See progression service/route; normal enrollment cannot bypass. | Preview/approve; retain old marks/enrollments; student sees own decision only. |
| Imported students rejected | Correct CSV/XLSX headers, no formulas, unique global login IDs/emails, correct cohort and prerequisites. Commit token expires and must match preview. See student_imports.py. | Bad batch creates zero accounts; corrected reviewed batch succeeds. |
| Subscription unexpectedly freezes | Recorded due date, five-day grace, manual freeze/status and Kenya midnight rules. See subscriptions.py; reconcile payment ledger before changing access. | Institution restored through recorded payment/unfreeze; other tenants unaffected. |
| Emails never arrive | Resend key, verified sender, recipient, delivery logs; distinguish contact enquiries from official-institution billing emails and invitations. | Real controlled recipient confirms receipt and recovery/invite flow. |
| Restore unavailable/fails | Dedicated BACKUP_SIGNING_KEY, matching archive key, supported pg tools, permissions, separate empty recovery DB and fresh authorized preview. See backups.py. | Restore drill on isolated destination; historical conflicts rejected. Never replace running DB directly. |
| Sidebar stretches / phone overflow | DashboardLayout.css, role nav and page-local CSS; wide tables should scroll inside panel or use mobile record layout. | Desktop, phone, keyboard and long names. |

## Local reference commands

From backend, with an isolated test/development environment:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_progression.py -q
.\venv\Scripts\python.exe -m pytest tests -q
```

From frontend:

```powershell
npm run lint
npm run build
node --test tests/*.test.js
```

Before any Alembic command, verify which database both DATABASE_URL and DATABASE_URL_UNPOOLED select. Local `backend/.env` can point to a hosted database. `preview.py` requires an ignored local `.env.preview` override; do not assume every other command loads that override. Tests use isolated SQLite and do not test hosted migrations.

## Repair discipline

Reproduce on synthetic data, identify the failing layer, fix the narrow cause, add a meaningful regression test, run relevant checks and document the outcome. Do not solve errors by disabling CSRF, widening tenant access, bypassing eligibility, editing historical grades directly or stamping a database revision without executing verified migrations. If data exposure is suspected, restrict affected access, preserve evidence and follow SECURITY.md.
