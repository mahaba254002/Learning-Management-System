# Operations records and handover templates

Copy these templates into your access-controlled operations tracker. Keep secrets and identifiable institution/student data out of the repository. Unfilled entries mean unknown, not passed.

## Deployment inventory

| Item | Verified value / private reference | Verified by / date |
| --- | --- | --- |
| Production frontend URL/account/Worker and version | To verify | |
| Production API service/account/linked branch and commit | To verify | |
| Production DB project/branch/database and Alembic revision | To verify privately; never paste URL/password | |
| Redis and billing cron service identifiers | To verify | |
| Sender verification and controlled email delivery evidence | To verify | |
| Backup location/key version/retention and restore drill | To verify privately | |
| Recovery-time and data-loss objectives | To agree | |
| Release/incident owner and escalation contact | To assign | |

## Release checklist record

- Release ID, date/time (Africa/Nairobi), owner, reviewer and immutable commit:
- Previous API/frontend versions; database before/after revisions:
- Changed features and migration files; compatibility review:
- Staging database provenance and privacy restrictions:
- Test commands, results and evidence location:
- Restore drill, backup timestamp/checksum/private location:
- Configuration checks (names/status only), sender delivery evidence:
- Maintenance window and paused/resumed jobs:
- Deployment start/end, actual hosting versions:
- Four-role/two-tenant smoke checks, mobile/accessibility results:
- Observation thresholds/results and go/no-go decision:
- Rollback/forward repair plan and unresolved issues:

## Error / incident record

- Time, environment, release version and incident owner:
- Page URL, role and redacted institution reference:
- Expected result, observed result and exact reproduction steps:
- Request method/path/status; redacted response and server log reference:
- Scope/impact: affected users, data integrity or possible exposure:
- Relevant component/route/service/model/test (from CODE_MAP/ROUTE_REFERENCE):
- Root cause, narrow fix, regression test and verification:
- Recovery actions, data reconciliation, resolution time and follow-up:

## Improvement record

- Roadmap item/priority, owner, target date and customer need:
- Dependencies and affected modules:
- Acceptance criteria, security/accessibility/data-integrity checks:
- Validation evidence, release version and documentation updates:
