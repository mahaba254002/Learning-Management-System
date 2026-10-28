# Using Skynet

## Sign in

Open the home page and choose Teacher or Admin. Platform and institution administrators share the Admin option and use email/password. Pupils select **Student login** and enter the email or unique student ID assigned by their institution administrator, plus their password. A temporary password requires changing before you can continue.

Passwords require at least eight characters, an uppercase letter, a lowercase letter, a number and a symbol. Password recovery uses your registered email. Pupils without email must ask their institution administrator for a password reset. Contact the administrator if your account is suspended or its details are incorrect.

## Students

1. **My subjects:** open an enrolled subject to read published material.
2. **Assignments:** open an assessment, read its deadline and instructions, then save a draft or submit a written response/document link. Confirm the submission receipt. Drafts are private; submitted work cannot be edited. Late submissions depend on the teacher’s policy.
3. **Attendance:** review your own subject attendance.
4. **Grades & feedback:** review scores and comments after results are released.
5. **My profile:** check your details and ask authorised staff for corrections.

## Teachers and class supervisors

Use your assigned subjects to publish materials, create coursework, mark subject attendance and enter scores. Coursework can stay in draft until ready for students. Review final submissions from the assessment’s score page. Check maximum marks before entering scores. Saving marks does not release results: use **Release results to students** when marking is ready.

Class supervisors can open their class roster, edit basic student details, enroll or withdraw existing students, and view all subject marks in their class's academic overview. Institution administrators create accounts and control sign-in details. Withdrawing a student preserves historical records. Authority is limited to assigned subjects and supervised classes.

## Institution administrators

Configure teachers, classes and subjects, then assign teachers and supervisors. Use invitations for teacher onboarding and class rosters for enrollment. The attendance, coursework, materials and scores sections provide institution-wide academic oversight. Use account controls carefully: suspension prevents access and invalidates prior sessions. Settings and audit logs support day-to-day administration.

## Platform administrators

Create institutions and their administrators, manage institution status, and inspect platform users, usage and audit events. Archiving requires email verification. Archived institutions cannot be restored through the current status controls.

Open an institution name to view its accounts, attendance and subscription. Configure a monthly KES subscription, five-day grace period and support email, record verified payments, or freeze access manually. The due date automatically controls academic access when enforcement is enabled. See [Institution product operations](INSTITUTION_PRODUCT.md) for learning settings, payment rules, reminder setup and rollout boundaries.

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
