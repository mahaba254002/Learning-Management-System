# Student learning workspace

Students enter at `/student/dashboard`. Navigation includes all currently enrolled subjects, subject materials, assignments and tasks, attendance, grades and feedback, and a read-only profile. The dashboard highlights outstanding work and deadlines.

## Learning workflow

- Teachers publish lesson text and web resource links from **Course materials**, scoped to subjects they teach. Unpublished materials stay hidden from students.
- Students save private drafts and submit typed answers or document links. They must grant their teacher access to linked documents. Binary file uploads are not included.
- Final submission requires review and confirmation, receives a timestamp and receipt, and locks editing. Version checks prevent an old browser session from overwriting a newer draft.
- Teachers choose whether late submissions are accepted. Accepted late work is labelled; closed deadlines still allow private draft saving. Examinations use teacher instructions rather than online submission.
- Teachers see final submissions within **Scores**, alongside marks and feedback. Draft answers are never returned to staff. Scores, including zero, and feedback appear to the individual student.
- Attendance shows each enrolled subject, daily class records, and individual history. The displayed percentage counts present and late as attended, excludes excused sessions, and shows no percentage when no countable records exist.
- The profile displays identity, contact details, admission number and classes without an edit endpoint. Password changes use the existing separate security flow.

## Access and retention

Identity and institution come from the authenticated session. Every student resource requires their active class enrollment; other students' answers and scores are never included. Removing enrollment hides that class's learning resources while retaining historical records. Materials and submissions have composite tenant foreign keys. Only assigned subject teachers or institution administrators can manage materials or review submitted work.

Final work cannot currently be reopened or resubmitted. Quizzes, weighted grade totals, notifications, file storage, and lesson-period attendance are outside this implementation.

## Deployment and validation

Migration `a3c4d5e6f7b8` follows `f2b3c4d5e6a7`. It creates course materials and assignment submissions, and adds the late-submission policy to coursework. Deploy the backend and frontend together after applying the migration through the normal deployment process.

On September 30, 2026, upgrade, downgrade and re-upgrade passed on the existing disposable Neon validation branch. All nine academic/learning tables matched model columns, types, nullability, foreign keys, unique constraints and indexes. Existing academic, user, teacher and institution row counts were preserved. Production was not migrated for this feature.

Validation completed: 40 backend tests (`tests/test_teaching.py` and `tests/test_learning.py`); 15 frontend tests (`tests/portal-routing.test.js` and `tests/student-learning.test.js`); frontend build and lint. Synthetic browser checks verified dashboard navigation, saved draft persistence after reload, final review, and a locked timestamped receipt. The final teacher-review browser check was interrupted by browser access policy; teacher review permissions and response content passed HTTP tests.

Run backend tests with the development dependencies in an isolated Python environment. The test fixture overrides the database URL and signing key and uses synthetic SQLite data. `scripts/validate_teaching_migration.py` now validates this student migration; disposable mode deletes materials/submissions during its rollback and must only target an isolated branch. Never use disposable mode on production.

The migration validator now targets the later administrator audit migration. See ADMIN_WORKSPACES.md for its current behavior and deployment order; its disposable rollback deletes audit events only.
