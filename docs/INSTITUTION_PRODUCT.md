# Institution learning and subscription operations

## What is implemented

- Institution types include kindergarten, primary, high school, college, university, training institution and other.
- Institution Settings → Learning configuration controls learner/educator/class/subject/period labels, default student login and optional grading bands. College/university defaults use Lecturer, Cohort and Course; kindergarten/primary defaults use Pupil and student-ID login. These are editable defaults, not an official curriculum or grading policy.
- Institution administrators create student accounts in Classes → class roster. Select email or student-ID login per account. ID-only accounts do not need a placeholder email. Admission numbers remain institution-local records; login IDs are globally unique, case-insensitive ASCII identifiers, stored uppercase. A duplicate ID is rejected rather than selecting an institution implicitly.
- Institution administrators can change a student's sign-in method and reset their password from Manage sign-in. Both revoke earlier sessions. Reset generates a temporary password and requires a first-login password change. Share credentials securely and dismiss the result. Student password recovery by email is available only to accounts with an email address.
- Class supervisors manage enrollment and basic student details, view daily registers and read marks across every subject in their supervised class. Account creation and credential administration belong to the institution administrator. Subject teachers can enter marks only for their assigned subjects.
- Publishing an assessment makes instructions available. Results release is a separate operation on the Scores page. Both marks and feedback remain hidden until release; results can be withheld again. Existing published marks retain their visibility when migrating.
- Institution-approved percentage bands produce result labels. Without bands, results use numeric marks. No KCSE, competency or university GPA conversion is assumed.
- Platform dashboard institution names open a detail page: scoped account search, workspaces, attendance, subscription configuration and payment history. Institution directory and account searches have server-side pagination.
- The platform dashboard also separates institution lifecycle status from subscription access status and totals payments actually recorded for the current Kenya calendar month. These are manual ledger totals, not confirmed M-Pesa settlements.
- Charts use persisted records and include a data table alternative. Main dashboards and class reports refresh every 30 seconds while open. They are polling views, not a WebSocket stream. Daily attendance summaries exclude subject registers to avoid counting the same school day twice.

## Subscription rules

Configure a subscription from Platform → Institutions → institution name. Currency is KES. Existing institutions have enforcement disabled until configured. Enabling enforcement requires a due date and support email. The default grace period is five days.

Deadlines use Africa/Nairobi calendar dates. A payment due on 1 October with five grace days freezes access at 00:00 on 6 October. Every protected academic request checks the current subscription, so enforcement works even if a reminder worker is down. Existing sessions are blocked too. The frozen screen and login rejection show the configured support address, initially mahaba955@gmail.com. Institution records are preserved.

Manual freeze is separate from automatic overdue freeze and from institution suspension/archive. A received payment advances the next due date but does not clear a manual freeze. Platform administrators retain access for support and billing; institution accounts remain blocked. An inactive or archived institution remains inactive regardless of payment.

Record verified payments with amount, date, unique reference and the next agreed due date. This does not collect money or integrate M-Pesa. Payment records are append-only through the API. Duplicate references are rejected, and stale due dates produce a conflict. Subscription changes and payment recording are serialized on the institution row and audited under the real administrator.

## Reminder delivery and deployment

The reminder command is `python billing_reminders.py` from `backend`; the default is a dry run. `--send` delivers notices to each institution's official email three days before the due date, when overdue, and when frozen. Notices use durable keys per due date/stage. Failed sends remain retryable. Delivery is at least once: a crash after sending but before committing may repeat one notice. Run one scheduled worker. Missing official email is reported as a failed run instead of silently pretending delivery.

An optional hourly Render service definition is in [deploy/render-billing.yaml](../deploy/render-billing.yaml), following [Render's cron job configuration](https://render.com/docs/cronjobs). Deploy it only after the API migration, with the same database and verified email credentials. It is not deployed by local development or the main Blueprint. No live reminder emails were sent during implementation. Request-time freezing does not depend on deploying this worker.

Migration: `c5e6f7a8b9d0`. Test against an isolated PostgreSQL branch/copy before running `alembic upgrade head` with the direct connection in `DATABASE_URL_UNPOOLED`. It adds nullable student emails, login constraints, case-insensitive unique emails, learning settings, results release and subscription tables. Resolve any existing email addresses that differ only by letter case before migration. Downgrade refuses to make email mandatory while ID-only accounts exist; assign valid unique emails first. PostgreSQL retains the added KINDERGARTEN enum value on downgrade.

## Local preview used for QA

The hosted database was exported read-only and restored to a separate local PostgreSQL database `skynet_preview` on `127.0.0.1:55432`. The migration and synthetic `Skynet QA School` records were applied only to that copy. The API runs on 8010 and Vite on 5174, with the API process configured to use the local copy. The original `.env` and hosted database are unchanged. Changes made in this preview do not synchronize to the hosted database.

To restart this preview from `backend`, use `.\venv\Scripts\python.exe preview.py`. It loads ignored `.env.preview` overrides and refuses an external database host. Ensure the local PostgreSQL instance on 55432 and Redis on 6379 are running. From `frontend`, use `npm run dev -- --host 127.0.0.1 --port 5174 --strictPort`. Do not restart the preview through the ordinary backend command without its local overrides: the original `.env` still targets the hosted database.

## Remaining product boundaries

This implements the shared learning and subscription workflows. Institution-specific GPA/credit rules, programme/department structures, official competency transcripts, guardian access, binary document uploads, timetabling, school-fee accounting and M-Pesa collection need their own agreed rules and implementation. Link/text assignment submissions already work. A production rollout also needs verified email delivery, a deployed reminder worker, backup/restore exercises and representative institution acceptance testing; passing local tests is not a production security certification.
