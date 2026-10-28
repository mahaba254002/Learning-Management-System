# Pilot workflows

Available in the local preview; not deployed to the hosted service. Use synthetic records until deployment configuration, privacy arrangements and operational checks are complete.

## Sessions

New logins create a revocable server session. Access lasts 15 minutes; refresh has an absolute seven-day expiry by default. Refresh rotates its credential, rejects replay, preserves session-cookie versus Remember me behaviour, and never extends that absolute expiry. CSRF, current account/institution status, password-change revocation and subscription restrictions are checked again. Logout revokes the server session even when access has expired. Sessions issued before this migration require one new login when their original access expires.

The browser renews once after an authentication failure and retries the original request once with its original body and fresh CSRF headers. One tab shares a renewal; browsers with Web Locks serialize renewals across tabs. Other browsers can require signing in again when tabs race; refresh replay is still refused. Wrong passwords and authentication actions are not automatically retried. Network failures do not trigger blind mutation retries.

When renewal expires, the workspace stays mounted behind a password dialog. Sign in to the original account and retry saving. Reauthentication does not extend delegated workspace grants; expired workspace access requires returning to the original workspace and reopening delegation.

## Unfinished work

Attendance, marks, assessment authoring and assignment answers have private server recovery drafts. Changes save after 600 ms without typing and are flushed on normal route changes. Wait for the saved indicator before closing. Network failures show an error and unsaved changes trigger a browser unload warning. This is online recovery, not offline synchronization: work never received by the server cannot survive a forced browser/device shutdown.

Drafts are scoped to real actor, effective account, resource and date/assessment. Read-only delegated views cannot save. Student recovery drafts are not submissions and are not shown to teachers. Explicit Save draft and Review & submit actions remain separate. No learner answers or passwords are persisted in localStorage. Draft versions prevent silent replacement by another tab. Attendance/mark revisions and assignment/assessment versions reject stale academic saves. Review current records before retrying.

Drafts expire after 30 days when accessed. Deployment housekeeping should remove unused expired drafts and expired/revoked sessions. Institution exports include calendars but exclude private drafts and live sessions. Full database backups contain them and revoke recovered credentials.

## Student imports

Institution sidebar → **Import students**. Select a destination class and upload UTF-8 CSV or one Excel worksheet (`.xlsx`). Limits: 2 MB uploaded, 10 MB expanded workbook, 500 students. Formulas, unexpected/duplicate headers and extra columns are rejected. Keep IDs as text to preserve leading zeros. Replace the fictional example rows in the downloadable template.

Columns: `first_name`, `last_name`, `admission_number`, `login_method`, `login_id`, `email`, `phone`. The first four headers are required. EMAIL rows require email; STUDENT_ID rows require a globally unique login ID. ID-only pupils may omit email. Admission numbers remain institution-local.

Validate and preview checks field values, file duplicates, institution admissions and global identity conflicts. Download row-level errors, fix the source file and upload again. Invalid previews create no accounts. A valid preview expires after ten minutes and is bound to actor, institution, class and exact rows. Commit revalidates and creates users, profiles and enrollments atomically. Existing students are not overwritten; use class enrollment for them.

Each account receives a unique generated temporary password and mandatory first-password change. Download credentials immediately after successful import and distribute them privately. Readable passwords are not retained and the download cannot be recreated from hashes; use student password reset if it is lost. Spreadsheet exports escape formula-like values. Audit events record counts/class IDs, never passwords.

## Academic years

Institution sidebar → **Academic years**. Create a uniquely named year with explicit dates; add non-overlapping terms or semesters inside it. Dates for existing class years are not guessed: create a calendar with exactly the existing year name to adopt those classes. Class year labels cannot be changed to move historical records; create destination classes instead. Year names and dates are fixed in this initial workflow, so review them before saving.

Years cannot overlap. Only one can be ACTIVE. PLANNED years allow setup; activation requires a term/semester. Teaching offerings can now link to a period in their group's academic year; legacy records without a period remain readable. See [Academic configuration](ACADEMIC_CONFIGURATION.md).

Review supervision, unpublished assessments, missing marks, released results and class reports before closure. Only institution administrators (or platform administrators in full-access institution workspaces) can close an ACTIVE year with its confirmation phrase. Published assessments must have marks for every current enrollment and released results. Closure locks class/enrollment, subject, attendance, assessment, material, marking and student-submission writes. Existing records stay readable. Closure cannot be undone in this UI; privileged backup recovery remains separate.

For promotion, first create a later open year and destination classes. In the CLOSED source year, map every class to its next class or explicitly Completed/leaving. Preview counts and confirm. The ten-minute actor-bound plan rejects changed classes/enrollments. One promotion is allowed per source year. Destination enrollments are added/reactivated; source enrollments, attendance, submissions and marks remain as history. Accounts, marks and assignments are not duplicated. Assign destination teachers and subjects separately. This legacy workflow moves whole classes and is available only when individual progression is disabled. When enabled, use [Student progression](STUDENT_PROGRESSION.md) to review advancement, repetition and completion per learner.

## Verification and remaining readiness work

HTTP tests cover renewal/replay/expiry, CSRF, logout, status/password revocation, private draft versions, import parsing/provisioning/rollback, role/tenant boundaries, calendars, closure locks, promotion review and historical enrollment preservation. Frontend tests cover request retries and revisions. PostgreSQL upgrade/downgrade/schema checks run on an isolated local database before preview upgrade. Browser tests use the actual React/API/PostgreSQL/Redis stack with synthetic records.

Scheduled offsite backups, MFA, live email delivery, broad load/accessibility testing and period-specific academic reports remain separate work. Programme/catalogue records, individual course registration, competency outcomes, approved credits, final grades/GPA, transcripts, prerequisites and reviewed individual progression are implemented. See [Student progression](STUDENT_PROGRESSION.md) for rules, safeguards and current limits. See [Academic configuration](ACADEMIC_CONFIGURATION.md) for the current implementation and remaining work. These changes alone do not certify production readiness.
