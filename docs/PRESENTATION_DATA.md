# Production presentation records

On 29 October 2026 the owner clarified that realistic fictional profiles should be loaded into production for a manager presentation. This supersedes the earlier instruction to keep fictional records in staging only. These records are fictional; they are not imported institutional records or a claim of affiliation with the school whose name the owner supplied.

`backend/scripts/seed_presentation.py` prepares Alliance High School with one institution administrator, three teachers, twelve students, two classes, three reporting terms, six subject offerings, learning materials, assignments, attendance and released weighted results. Names include Reed McDonald and Ali Salim. Account emails use aliases of the owner's `mahaba955@gmail.com` inbox, avoiding invented mailboxes belonging to other people. Six students use email login and six use assigned student IDs. The operation sends no email and records no subscription payments.

The script refuses a nonempty institution database or unexpected existing users, validates the exact target host and migration revision, and retains the existing platform owner's password. The default operation rehearses the whole import and rolls back. `--apply` requires a pre-import checkpoint. New accounts receive unique random passwords and initially require a password change. The private live verification helper exercises the normal login/password-change process for selected presentation accounts; the private credential sheet records their current passwords.

The complete import was rehearsed and rolled back against isolated Neon staging before production. A production connection failure before commit rolled back without partial records. The script uses one transaction, PostgreSQL constraints and an advisory lock. SQL errors suppress bound parameters so password hashes are not printed. If it fails, inspect the error and current counts before retrying; do not remove the empty-database guards to force a repeat.

The subsequent production import committed successfully. Read-only checks verified one institution, 17 total users (including the original owner), three teacher profiles, twelve students, 120 attendance records, 72 scores and 36 released final grades. The original owner's password hash is unchanged and there are no `.test` accounts. Live API checks passed for institution administrator Salim Hassan, teacher Grace Muli, email-login student Reed McDonald and student-ID user Ali Salim: normal login/password change, populated dashboard, linked role pages, released student final grades and denial of platform-only access. No account passwords are stored in this document or Git.

Recovery material lives outside Git in the access-restricted folder `C:/Users/mahab/.codex/skynet-release-backups/20261029T073222Z/`:

- `before-presentation-data.json`: a consistent, read-only snapshot of every nonempty public table and all public table counts, taken immediately before import. It contains the one retained platform owner and zero institutions. SHA-256: `092a3ccc244eadec9a10c35502557a009ad16445fe76d48810ecca74db080971`.
- The existing native `live-pre-upgrade.dump` supplies the validated full schema/data archive from the earlier cutover. The data checkpoint records schema revision `j2f3a4b5c6d7`; it is not itself a schema dump.
- `production-presentation-accounts.json`: private account credentials and created-record counts; never upload or commit it.
- `Skynet-production-logins.csv`: private login sheet generated after live verification; remaining untested accounts retain the initial password-change requirement.
- `presentation-live-checks.json`: verification results, without passwords.

An additional native dump and a provider snapshot request timed out before this import; they are not valid backup evidence. The consistent data checkpoint and earlier validated archive were retained instead. To recover, first use a separate empty database, apply the reviewed schema, restore the checkpoint rows in dependency order, verify the owner and counts, and only then switch application database settings. Do not restore over an active database.

Before onboarding actual customers, deliberately retire or replace this fictional institution through the normal administrative workflow and retain an appropriate audit record. Do not mix presentation scores, attendance or identities into actual student records.
