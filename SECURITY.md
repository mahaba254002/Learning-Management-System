# Security and public repository boundaries

Do not publish passwords, signing keys, API keys, database connection strings, cookie jars, production account directories, student records or operational account-repair scripts. Use environment variables and hosting secret settings. `.env.example` contains placeholders only.

The repository ignores local environments, generated files, credential/debug payloads and private maintenance scripts. Ignoring a file does not remove it from Git history. A cleanup of the current tree is not credential rotation or historical erasure.

## Historical exposure

Older revisions contained authentication/debug artifacts and a maintenance script with a hardcoded password. Treat credentials and sessions in those revisions as exposed. Owners should revoke or rotate any still-valid values and review access. Coordinate any Git history rewrite with collaborators; do not assume deleting the latest file makes an earlier credential safe. Do not copy exposed values into issues or pull requests.

## Reporting

Do not include a working exploit against the hosted service, credentials or personal records in a public issue. Use a private reporting channel offered by the repository owner. If none is configured, first ask the owner to establish one without disclosing sensitive details.

## Operational limits

Automated tests cover specific access-control and data-integrity scenarios; they are not an independent security audit. Keep dependencies reviewed, use HTTPS and production cookie settings, validate migrations on an isolated database, and check backup/restore and email delivery before using real learner records.

New logins use server session IDs with a hashed rotating refresh credential and an absolute expiry. Refresh is CSRF-protected, rechecks account/institution/subscription status and rejects replay. Logout revokes the session; password changes/recovery timestamps invalidate issued credentials. Private recovery drafts are scoped to both real actor and effective user, checked against current teaching/enrollment permissions, versioned and excluded from institution exports. Import review grants bind actor, institution, class and rows; account creation and enrollment commit together. Year closure and promotion are institution-admin operations with reviewed transitions and immutable source academic records. Details and limitations: [Pilot workflows](docs/PILOT_WORKFLOWS.md).


## Hierarchical workspace access

Workspace access uses a separate, short-lived signed grant bound to the real authenticated actor and a target account. The browser holds it in memory, not local storage. The original HttpOnly authentication cookie is retained. Each protected request validates the real account/session, the grant, active account/institution/profile status and the current hierarchy relationship. Teachers require active enrollment in an assigned or supervised class; institution administrators stay inside their institution; platform administrators may access lower roles across institutions.

Teacher and institution administrator views reject all mutations at the API boundary, apart from workspace entry/exit controls. Editing forms are also disabled while navigation and filters remain usable. Platform administrator views permit target-workspace actions and record mutation attempts with the real actor; existing administrative audit events also preserve that real actor and identify the effective account. Entry and exit events are recorded. Delegated views cannot change account passwords. Permissions are recalculated rather than trusted from a client-provided mode flag.

## Student identities and subscription access

Student login IDs are globally unique and normalized to uppercase. Emails have a case-insensitive unique index. ID-only pupils can have a null email; database checks still require an email for staff and a valid configured identity for every account. Student sign-in enforces the account's selected identity method. Institution administrators alone provision accounts, change login methods and reset student passwords. Identity changes and resets revoke prior sessions and are audited without recording passwords.

Result scores and feedback are filtered at the API until results are released. Class supervisors can read marks across their supervised class without gaining authority to edit other teachers' assessments.

Subscription freezing is checked at sign-in and on protected academic requests, including existing sessions. Only the real platform administrator retains delegated academic access for support while an institution is frozen. Student/teacher subscription-status responses exclude payment references and financial records. Payment/configuration writes are platform-only, tenant-scoped and audited. A manual freeze remains in effect after payment until explicitly cleared.

## Backup and recovery

Only platform administrators can export or restore. Archives are HMAC-authenticated with payload checksums and strict type/tenant validation before use. They include sensitive data and password hashes and are not encrypted; store downloads securely. Production requires a separate backup signing key. Restore uses an actor-bound, expiring review/authorization grant, a matching file hash, explicit confirmation and current-password verification. Institution merges are transactional, preserve records absent from the backup, reject cross-tenant identity collisions and refuse to rewrite existing financial history. Recovery revokes sessions and pending access links.

Full PostgreSQL snapshots restore only into a separately configured empty recovery database; the API does not switch the live connection. Backup/recovery subprocesses use argument arrays, credentials in the environment, configured tool paths, timeouts and private temporary files. No uploaded path or shell command is executed. Audit metadata uses the ASGI peer and omits raw secrets; reverse-proxy forwarding trust must be configured at the deployment boundary.
