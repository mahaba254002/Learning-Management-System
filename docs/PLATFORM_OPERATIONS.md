# Platform administration and recovery

The institution directory now shows institution name/code/type, contact email/phone, all institution administrators, next subscription due date, lifecycle status and subscription access. Search accepts institution name, code, email or phone; apply a status filter with Filter and reset it with Clear. Results remain paginated on the API.

The sidebar takes its layout cues from the separately inspected Alpha Harness project: a viewport-height navigation area, icon links, collapse control and pinned account section. Only the main workspace scrolls with page content; long navigation lists scroll independently. Mobile keeps the menu button on the right and supports Escape. A keyboard skip link reaches the workspace. No Alpha Harness files or services were changed.

## Audit logs

Action type filtering works for both platform and institution administrators. Rows show actor identity, event time and observed client IP. Expand View details for event ID, actor ID, target, institution, request method/path and descriptive detail. Old events have no reconstructed IP or request metadata and display Not recorded.

Request metadata comes from the ASGI request peer, not directly from visitor-supplied forwarding headers. The local preview disables forwarded-header trust and records loopback addresses. In production, configure the reverse proxy and ASGI trusted-proxy allowlist together, and strip untrusted forwarding headers at the ingress. An IP is contextual audit evidence, not an authorization credential. User credentials, access tokens and submission contents are not added to audit detail.

## Billing

Billing has its own sidebar page with recorded monthly payment totals, grace/frozen subscription counts, subscription chart and institution due dates. Open an institution to configure its subscription or record a verified payment. The previous five-day grace rule and separate manual freeze controls remain unchanged.

## Institution backups

Backup → Institution Backup exports a signed ZIP containing a manifest and `data.json`. Select learning, attendance and/or billing records. Accounts/profiles and class/subject/enrollment records are always included so relationships remain valid. Exports are scoped to the selected institution and use a consistent PostgreSQL repeatable-read snapshot. Platform-admin accounts are excluded; invalid platform membership prevents export. Active invitation secrets and verification codes are not exported in this format.

Restore accepts an original signed archive, checks its signature/checksum and validates record types and tenant IDs. The preview shows its destination, record counts and restore mode. Confirmation requires the displayed phrase plus the current platform administrator password. The resulting short-lived grant is bound to that actor, file and reviewed database state.

Institution restore merges backed-up records in one transaction. Matching records can be replaced; records absent from the backup are retained. Existing institution lifecycle status is preserved; an archived existing institution cannot be restored through this flow. A changed database state requires a fresh preview. Cross-institution IDs, conflicting global identities or changed existing payment records reject the merge. A failure rolls back the merge. Existing payments are never rewritten. Audit history is retained and a new recovery event is appended under the real actor.

Institution recovery revokes existing institution sessions, consumes pending verification codes and expires pending invitations. Reissue invitations as needed. Current passwords are recovered from their stored hashes; no plaintext password recovery is provided.

## Full PostgreSQL backups and recovery

Full Platform Backup downloads a signed ZIP containing a manifest and a custom-format PostgreSQL `data.dump`. This is a PostgreSQL snapshot, not a SQLite `.db` file. Export uses `pg_dump`; recovery uses `pg_restore --single-transaction --exit-on-error`, without destructive clean/drop flags.

Full recovery requires an explicitly configured separate **empty** PostgreSQL database. The API refuses the active database, its pooled/direct alias, or a destination with public tables/views. Restore fills that recovery database and revokes recovered sessions/codes/invitations. It does not switch the running application's connection. Verify record counts, schema and sign-in first; then arrange the connection switch during an operational maintenance window. Reusing a populated recovery database is refused rather than silently replacing it.

Both archive formats authenticate their content; they are not encrypted. They contain private student records and password hashes, so store them in protected storage. No signing key is placed in the download. Losing or rotating the signing key without preserving it makes earlier archives unverifiable.

### Server configuration

- `BACKUP_SIGNING_KEY`: dedicated long random secret, required in production. Keep it separately in secure configuration/backups. Development can fall back to the existing signing secret, but a dedicated private preview key has been configured locally.
- `PG_DUMP_PATH`, `PG_RESTORE_PATH`: optional absolute tool paths. Otherwise use server PATH; local Windows development can discover PostgreSQL 18 in its installed location. Install client tools compatible with the database version. Missing tools disable full-backup capability and produce an explicit service error rather than a fake download.
- `DATABASE_URL_UNPOOLED`: preferred direct source connection for `pg_dump`; otherwise the application database connection is used.
- `RESTORE_DATABASE_URL`: separate empty PostgreSQL recovery destination, stored privately. Never enter a recovery connection string in the browser.

HTTP uploads are capped at 512 MB; institution JSON payloads are capped at 50 MB, and database subprocesses time out after 180 seconds. Hosting request-size/time limits can be lower. Larger systems should use managed backup/recovery tooling outside a browser request. No recurring backup schedule or offsite retention policy is enabled by this change.

## Validation

API tests cover role/CSRF boundaries, scoped exports, signature tampering, unsafe payloads, confirmation/password checks, changed files, stale reviews, actor-bound restore grants, transaction rollback, immutable payments, recovery-target guards, missing server configuration and audit filtering.

Browser tests exercised the running React/FastAPI/PostgreSQL/Redis stack: institution columns/filters, viewport-bound sidebar/collapse, Billing, signed downloads, institution merge, audit IP/action/details, full backup and restoration into a disposable database, and mobile navigation. Hosted data was unchanged. Local signing settings and test archives are ignored by Git.
