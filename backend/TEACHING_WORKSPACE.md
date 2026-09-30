# Teacher workspace

The teacher portal now has a dashboard, personal profile, class rosters, attendance registers, coursework, and assessment scores. Institution administrators configure classes and teaching assignments at `/institution/classes`.

## Permissions

- Institution administrators create classes and assign supervisors and subject teachers in their own institution.
- Class supervisors create student accounts, edit student names and phone numbers, enroll existing students by exact admission number, remove enrollment, and take the daily class register.
- Subject teachers view rosters, take subject attendance, create/edit/publish assessments, and enter scores only for their assigned subjects. Supervision alone does not grant assessment or score access.
- Students see published assessments and their own scores/feedback for active enrollments at `/student/dashboard`. Drafts and other students' marks are never returned.
- Every academic lookup is scoped to the authenticated institution. Unknown, foreign, and unauthorized resources return the same 404. Composite foreign keys also prevent cross-institution relationships in the database.

## Initial setup

1. Test migration `f2b3c4d5e6a7` on an isolated PostgreSQL/Neon branch using a direct connection. It follows `e1a2b3c4d5f6` and adds seven tables plus a composite uniqueness constraint on users; it does not remove any existing user columns.
2. Apply the reviewed migration as part of deployment (`alembic upgrade head` from `backend`). Deploy the API and frontend together.
3. Sign in as an institution admin, open **Classes & teaching**, create a class/session, assign its supervisor, then add subjects and their teachers.
4. Open **Manage students** to create and enroll students, or enroll existing students by admission number. New student accounts use the existing student login and forced password change flow. Temporary credentials are shown once for secure handover; no email is sent automatically.
5. Teachers sign in through `/teacher/login`. Their classes and subjects appear automatically.

Enrollment removal is reversible and retains the account, attendance and scores. Account email, role, admission number and passwords cannot be changed through the supervisor's student edit endpoint. These are deliberately separate from student name/contact edits.

## Validation

Install `requirements-dev.txt` into a working Python 3.12 environment, then run `python -m pytest tests/test_teaching.py -q` from `backend`. Tests override the database URL and signing key before importing the app, use synthetic accounts and an in-memory SQLite database with foreign keys enabled, and exercise actual HTTP authentication/CSRF dependencies. They do not connect to the configured live database.

Frontend checks: `npm run build`, `npm run lint`, and `node --test tests/portal-routing.test.js` from `frontend`.

On September 30, 2026, a temporary Neon branch (`teacher-workspace-validation-20260930`) was created from production. Downgrading from `f2b3c4d5e6a7` to `e1a2b3c4d5f6` and upgrading again both passed on that branch. Existing user, teacher and institution counts and all user columns were preserved. A subsequent read-only check verified the seven teaching tables against model column names, types, nullability, foreign-key targets, uniqueness constraints, and indexes. The branch expires October 2, 2026 at 06:00 UTC.

A read-only production check found the database already at `f2b3c4d5e6a7`. Detailed production schema verification also passed after a transient connection failure: all seven teaching tables match the model columns, types, foreign keys, uniqueness constraints, and indexes, and both password-security columns are intact. No production migration was executed by this validation. Deployed backend health and API-schema checks timed out, so deployment and live teacher-route availability remain unverified.

`scripts/validate_teaching_migration.py` now validates the subsequent student learning migration described in `STUDENT_LEARNING.md`. Supply `MIGRATION_TEST_DATABASE_URL` through the process environment, a matching `--expected-host`, and either `--read-only` or `--confirm-disposable`. **Disposable mode drops materials and submissions during downgrade; use it only on an isolated test branch.** Local `.env` files were not changed.

## Current boundaries

- One daily class register and one register per subject per date. A save supports up to 500 students.
- Assignments target all active students in the subject's class. Instructions are plain text, with an optional due date/time, draft/published state, and a maximum score.
- Scores support two decimal places, zero marks, and individual feedback. Saved scores for published assessments are immediately student-visible. Blank entries remain ungraded.
- This implements the requested teaching workspace, not a complete Moodle replacement: student file submissions, attachments, quizzes, grading rubrics, weighted term totals, lesson-period attendance, and notifications are not included.

The student learning extension adds published lesson text/resource links, private drafts, typed-answer/document-link submissions, submission receipts, and teacher review within Scores. See `STUDENT_LEARNING.md` for its workflow and deployment status.

The migration validator now targets the administrator audit migration described in ADMIN_WORKSPACES.md. Its current disposable rollback deletes audit events only; the earlier validation results above are retained as history.
