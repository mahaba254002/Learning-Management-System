# Maintenance handbook — start here

Reviewed against the working tree on 28 October 2026. The original product is already live. Recent feature verification describes the local working tree, not proof that the live site runs this release. No deployment or hosted database change was performed while writing this handbook.

## Find the right reference

| Need | Reference |
| --- | --- |
| Error on a page: which component, API and test? | [Code map](CODE_MAP.md), then [generated route reference](ROUTE_REFERENCE.md) |
| Diagnose and repair a failure | [Troubleshooting](TROUBLESHOOTING.md) |
| Step-by-step deployment and migration | [Execution checklist](DEPLOYMENT_MIGRATION_PROCESS.md) |
| Upgrade the existing live site | [Live deployment runbook](DEPLOYMENT.md) |
| What is missing or needs improvement? | [Prioritised roadmap](ROADMAP.md) |
| Record a release, incident or production configuration | [Operations records](OPERATIONS_RECORDS.md) |
| Academic structure and institution types | [Academic configuration](ACADEMIC_CONFIGURATION.md) |
| Sessions, drafts, imports and academic years | [Pilot workflows](PILOT_WORKFLOWS.md) |
| Reports, final grading, GPA and progression | [Reports](ACADEMIC_REPORTS.md), [grading](GRADING_RULES.md), [progression](STUDENT_PROGRESSION.md) |
| Billing, audit, backup and recovery | [Product operations](INSTITUTION_PRODUCT.md), [platform operations](PLATFORM_OPERATIONS.md) |

## Follow an error through the system

Browser page → React component → shared API client → same-origin Cloudflare `/api` proxy → FastAPI route → access checks → service rules → database model/migration. Redis supports rate limiting and verification; Resend delivers email. A failure at an earlier layer can prevent all later code from running.

Use the browser Network panel to capture the failed URL, method, status and redacted response. Search that endpoint in the route reference; follow its code link and function name. Use the code map to find the relevant service and regression test. Preserve existing validation and access checks when fixing a problem.

## Evidence and limits

The last feature release passed 301 isolated backend tests, 31 frontend tests, lint/build, disposable PostgreSQL migration checks, and connected browser workflows for kindergarten, primary, college and university. This is a dated baseline, not a claim that every future commit or production environment passes. Tests substitute external services; real email delivery, production recovery, load and broad accessibility acceptance still need separate evidence. Ignored local `.env.*` QA helpers are machine-specific, not a portable deployment toolchain.

## Keep documentation useful

For each behaviour change, update the affected feature guide, roadmap status and release record; add a regression test for a real failure. Regenerate ROUTE_REFERENCE.md using `python scripts/update_reference.py` from the repository root. File/function links are preferable to hard-coded line numbers because lines move. Never put passwords, tokens, student records, database URLs or private deploy hooks in documentation or incident screenshots.
