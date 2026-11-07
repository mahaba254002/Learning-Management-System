# Using Skynet

## Sign in

Open the home page and choose Teacher or Admin. Platform and institution administrators share the Admin option and use email/password. Pupils select **Student login** and enter the email or unique student ID assigned by their institution administrator, plus their password. A temporary password requires changing before you can continue.

Passwords require at least eight characters, an uppercase letter, a lowercase letter, a number and a symbol. Password recovery uses your registered email. Pupils without email must ask their institution administrator for a password reset. Contact the administrator if your account is suspended or its details are incorrect.

## Students

1. **My subjects:** open an enrolled subject to read published material.
2. **Assignments:** open an assessment, read its deadline and instructions, then save a draft or submit a written response/document link. Confirm the submission receipt. Drafts are private; submitted work cannot be edited. Late submissions depend on the teacher’s policy.
3. **Attendance:** your attendance rate for each subject and the class register, by term or semester.
4. **Timetable:** your lessons this week, with any changes, and your class timetable once it is published.
5. **Announcements:** notices from your institution.
6. **Grades & feedback:** review scores and comments after results are released.
7. **My profile:** check your details and ask authorised staff for corrections.

## Teachers and class supervisors

Use your assigned subjects to publish materials, create coursework, mark subject attendance and enter scores. Coursework can stay in draft until ready for students. Review final submissions from the assessment’s score page. Check maximum marks before entering scores. Saving marks does not release results: use **Release results to students** when marking is ready.

Class supervisors can open their class roster, edit basic student details, withdraw students and restore students they withdrew, and view all subject marks in their class's academic overview. Institution administrators create accounts, add new students to classes and control sign-in details. Withdrawing a student preserves historical records. Authority is limited to assigned subjects and supervised classes.

**My timetable** shows your lessons for the week, including cancelled, moved and covered lessons. Use *Take attendance* on a lesson to open its register. For a late student, record the arrival time; a student who arrives close to the end of the lesson counts as absent unless you tick *Reason accepted* and write the reason. *Attendance percentages* on the Attendance page shows each student's rate per subject and term. Class teachers also get **Student records** (guardians, fee standing, discipline) and **Fee status** for their classes.

## Institution administrators

Configure teachers, classes and subjects, then assign lead teachers, co-teachers and supervisors. Add staff directly in the staff directory, with an optional sign-in that is set up through a single-use link, or use invitations. Use class rosters for enrollment. The attendance, coursework, materials and scores sections provide institution-wide academic oversight. Use account controls carefully: suspension blocks sign-in temporarily, deactivation is for people who leave, and archiving hides an account. Each ends existing sessions. Settings and audit logs support day-to-day administration.

**Requests to platform** asks the platform to delete an account, help with a password or account recovery, change your institution details, or anything else; follow each request until it is done. **My courses**, file uploads, **online quizzes** (timed, auto-marked, with anti-cheating rules), deadlines, the notification bell and **Course registration** windows are described in [E-learning](ELEARNING.md). **Parent messages** sends results, fee balance reminders and notices to guardians by SMS with an email copy; each send needs your secret question. See [Parent messages](PARENT_MESSAGES.md). **Marks & marksheets** and **Grading** are described in [Marks, grading and marksheets](MARKS_AND_GRADING.md): upload marks from Excel, download class marksheets, and set your grading once (later changes need platform approval). **Student records**, **Fee status**, **Announcements** and **Timetable** are described in [Student records and timetables](STUDENT_RECORDS_AND_TIMETABLE.md). Give a bursar the *View and update student fee status* right to keep fee status up to date.

Billing shows what is owed, payment history and how to pay. Pay with an M-Pesa phone prompt from the page, or through the paybill using your institution code as the account number. A banner appears three days before the due date. If payment is more than three days late, access pauses for everyone; you can still sign in and pay, and access returns as soon as payment is confirmed.

## Platform administrators

Create institutions and their administrators, manage institution status, and inspect platform users, usage and audit events. Archiving requires email verification. Archived institutions cannot be restored through the current status controls.

Open an institution name to view its accounts, attendance and subscription. Configure a monthly KES subscription and support email (the grace period is a fixed three days), record verified payments, or freeze access manually. The due date automatically controls academic access when enforcement is enabled. See [Institution product operations](INSTITUTION_PRODUCT.md) for learning settings, payment rules, reminder setup and rollout boundaries. Payment records lists every billing message and payment as tamper-evident evidence, with a CSV download.

## When something goes wrong

- **Incorrect credentials:** check your email, password and selected role. Passwords are case-sensitive.
- **Expired session:** sign in again before continuing.
- **Missing subjects:** ask staff to verify enrollment and subject assignment.
- **Email not arriving:** check spam and ask the administrator to verify email delivery settings.
- **Save failure:** read the message before retrying; deadlines, permissions or a newer saved version may prevent the change.

Contact your own institution for academic or account corrections. Do not share passwords, student records or screenshots containing personal information in public GitHub issues.


## View another person's workspace

Teachers open **My classes**, choose a class roster, then select **View workspace · read-only** beside a student. Access is limited to students actively enrolled in classes they supervise or teach.

Institution administrators open **Teachers** and select **View workspace · read-only**. They can inspect the teacher's classes, materials, coursework, attendance and scores, and open students from those class rosters. Their access remains read-only throughout, within their own institution.

Platform administrators open **Platform Users**, find an institution administrator, teacher or student, then select **Open workspace · full access**. Edits use that person's existing workspace permissions, with the platform administrator retained as the real actor in audit records. To work across a whole institution, open its institution administrator's workspace.

A banner always shows whose workspace is open and whether editing is allowed. **Return to my workspace** returns to the original signed-in account. Viewing does not require the other person's password or replace your login cookie. Delegated access lasts up to ten minutes and is rechecked on every request; a page reload returns to your own account. Account password changes require returning to your own workspace.
