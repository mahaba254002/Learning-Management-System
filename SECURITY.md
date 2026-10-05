# Security and public repository boundaries

Do not publish passwords, signing keys, API keys, database connection strings, cookie jars, production account directories, student records or operational account-repair scripts. Use environment variables and hosting secret settings. `.env.example` contains placeholders only.

The repository ignores local environments, generated files, credential/debug payloads and private maintenance scripts. Ignoring a file does not remove it from Git history. A cleanup of the current tree is not credential rotation or historical erasure.

## Historical exposure

Older revisions contained authentication/debug artifacts and a maintenance script with a hardcoded password. Treat credentials and sessions in those revisions as exposed. Owners should revoke or rotate any still-valid values and review access. Coordinate any Git history rewrite with collaborators; do not assume deleting the latest file makes an earlier credential safe. Do not copy exposed values into issues or pull requests.

## Reporting

Do not include a working exploit against the hosted service, credentials or personal records in a public issue. Use a private reporting channel offered by the repository owner. If none is configured, first ask the owner to establish one without disclosing sensitive details.

## Operational limits

Automated tests cover specific access-control and data-integrity scenarios; they are not an independent security audit. Keep dependencies reviewed, use HTTPS and production cookie settings, validate migrations on an isolated database, and check backup/restore and email delivery before using real learner records.
