# Populated learning dataset

The production sample institutions are Acacia Secondary School and Harbour Academy (active), Ridgeway Training Institute (suspended) and Lakeview College (archived). User-facing names, usernames, institution codes, class names and admission numbers contain no "demo" labels. These are sample records with realistic names; contact emails remain on the reserved example.test domain so no messages reach unrelated people.

The dataset contains 49 seeded accounts, 8 teacher profiles, 36 student profiles/enrollments, 4 classes, 12 subjects, 36 materials, 72 assessments, 156 submissions, 168 marks, 1,200 attendance records, 10 invitations and 4 seed audit entries. The previously unassigned QA student is additionally linked to Acacia and Form 1, with a student profile and active enrollment. Existing academic history is retained.

`SAMPLE_ACCOUNTS.json` is the non-secret account directory. Passwords are deliberately excluded. Four individually generated passwords are handed to the requesting user in chat; the selected accounts open directly into their role dashboards. They are Nathan Kimani (platform), Miriam Wanjiru (Acacia administrator), Grace Muli (teacher and Form 1 supervisor), and Amani Otieno (Form 1 student). Use the shared admin login for the first two, teacher login for Grace and student login for Amani.

## Repeatability and legacy IDs

`scripts/seed_demo.py` retains its legacy filename and UUID namespace to preserve the IDs and relationships of the original seed. Its visible values now use natural names. A normal rerun inserts missing generator-owned rows and preserves existing edits and passwords. `--rename-existing` explicitly updates the display fields on generator-owned legacy rows. It does not reset learning history or delete records.

`scripts/repair_seed_accounts.py --target production` applies this one-time rename, repairs only the specifically identified unassigned QA account if it still meets the repair conditions, and rotates the four checking accounts. It prints their requested credentials but never writes passwords into the repository. Do not rerun it unless password rotation is intended. `--target validation` exercises the rename on the isolated branch without creating credentials or modifying the QA account.

Database credentials are loaded from the existing local connection configuration and never printed. The production connection is unchanged. No emails are sent and no payment or verification-code history is fabricated.

## Student error correction

`qa.test.student` had no institution. Its account was assigned to Acacia and enrolled in Form 1; its original password and username are preserved and its full name is Ethan Mwenda. Existing sessions are invalidated following the institution change, so sign in again. Historical attendance or submitted work is not invented for this newly enrolled account. Amani Otieno has the fully populated student history for feature checks.

The authentication code also rejects non-platform accounts without an institution before issuing a login session, and rejects existing sessions for such accounts. This prevents the dashboard from opening into repeated missing-institution errors. This preventive code requires normal backend deployment; the production data repair works with the currently deployed API.

## Validation

58 backend tests passed, including seed relationships, counts, deadlines, score limits, repeatability, name conversion preserving learning history, missing-institution authentication, and role isolation. The rename was first exercised on the isolated PostgreSQL branch. Live role checks are performed after the production update and reported in chat.

Production verification on October 1, 2026: all four selected logins returned HTTP 200. Platform statistics/users/usage, institution overview/settings/users, teacher profile/classes/subjects, and student profile/subjects/attendance/assignments all returned HTTP 200. The selected student has 3 subjects, 40 attendance records and 15 published assessments. The QA repair committed successfully. Passwords are omitted from this document and the account directory.
