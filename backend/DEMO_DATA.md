# Fictional demo dataset

The repeatable generator is `scripts/seed_demo.py`. Every school name contains Demo, account usernames begin with `demo.`, and email addresses use the reserved `example.test` domain. No email is sent. The generator creates records only; it never deletes records, resets the database, changes the schema, or overwrites existing demo edits/passwords.

## Dataset

- 4 institutions: Acacia and Harbour are populated active schools; two additional institutions demonstrate suspended and archived states.
- 49 user accounts: one platform admin, four institution admins, eight teachers, and 36 student accounts. Student examples include suspended access and a forced first-login password change.
- 4 classes, 12 subject allocations, 36 student profiles and enrollments. Four students have withdrawn enrollments with retained attendance history.
- 36 course materials: 24 published lesson/practice notes and 12 teacher drafts.
- 72 assessments: marked practice, upcoming work, overdue work accepting late answers, closed deadlines, examinations, and unpublished teacher drafts.
- 156 submissions: private drafts, submitted work, and late submissions; 168 marks with feedback.
- 1,200 attendance records: ten preceding weekdays, daily class and subject registers, including present, late, absent and excused states.
- 10 teacher invitations covering sent, submitted, approved, rejected and expired states; 4 clearly labelled demo-seeding audit events.

Math, English and Science contain real instructional examples and matching answers. Attendance excludes weekends and future dates. Scores stay within each assessment maximum. Submitted work has timestamps consistent with its late flag. Withdrawn students retain older records but cannot access current learning resources. Invitations have random unprinted tokens; no live verification codes, delivery failures or payment records are fabricated.

`DEMO_ACCOUNTS.json` is the non-secret account directory and creation report. Useful usernames: `demo.platform`, `demo.acacia.admin`, `demo.acacia.teacher1`, `demo.acacia.student01`; substitute `harbour` for the second school's accounts. Use the admin, teacher and student login doors respectively. `student08` and `student16` demonstrate withdrawn enrollment; `firstlogin` demonstrates forced password change.

## Passwords and execution

There are no hard-coded or published passwords. Unattended seeding uses a strong random password that is not printed or saved. To log in, choose a demo password privately using `--set-demo-password`; it only changes users whose deterministic ID, username and fictional email match this generator, and invalidates their old sessions. It preserves forced-password-change flags.

Set `SEED_DATABASE_URL` securely in your process environment to the intended direct PostgreSQL connection. The script requires `--expected-host` to match that URL and requires schema revision `b4d5e6f7a8c9`. It never reads the application database URL as a fallback and never applies migrations. Supply database credentials through your environment/secret manager, not command-line arguments or checked-in files.

From backend, using a working Python environment with the project requirements:

```powershell
# Validate within a transaction and roll back (default).
python scripts/seed_demo.py --expected-host <direct-host> --date 2026-09-30
# Commit, prompting privately for the initial demo password.
python scripts/seed_demo.py --expected-host <direct-host> --date 2026-09-30 --apply --password
# Set a new password for existing generator-owned demo accounts.
python scripts/seed_demo.py --expected-host <direct-host> --apply --set-demo-password
```

Rerunning with a later reference date does not move existing deadlines or rewrite history. Unique deterministic IDs and a transaction advisory lock prevent concurrent duplicate creation. A failure rolls back the seed transaction. No production reset or removal option is provided.

## Current target

The September 30 seed targets the isolated Neon branch `teacher-workspace-validation-20260930`, direct host `ep-restless-king-b5mp4w10.c-7.us-east-2.aws.neon.tech`. This branch currently expires **October 2, 2026 at 09:00 Africa/Nairobi (06:00 UTC)**. Keep the generator to recreate the dataset after expiration. Production remains unchanged, and local connection files are not switched automatically.

Validation includes an isolated SQLite integration test checking counts, tenant relationships, enrollment, score bounds, attendance dates, submission timing, repeatability, preservation of edited demo records and real records, and the student/admin API views.

## Production selection

The user subsequently requested **Neon production**. The target is now the existing production direct connection in root `.env.local`, host `ep-ancient-unit-b5d1d24x.c-7.us-east-2.aws.neon.tech`. The isolated branch remains a validation copy; its expiry does not affect production. Connection files were not modified.

After seeding, choose the demo login password privately. From a working Python environment, at the repository root:

```powershell
python backend/scripts/set_demo_password.py --expected-host ep-ancient-unit-b5d1d24x.c-7.us-east-2.aws.neon.tech
```

This helper reads the already-configured production direct URL and asks for the password without echoing it. It neither prints nor writes the password. Only generator-owned demo users are changed; normal users are excluded. All demo accounts share the password you choose, so use this only for controlled demonstration access, and do not publish it.
