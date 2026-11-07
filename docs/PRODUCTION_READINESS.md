# Production readiness review (phase 12)

Reviewed on 7 November 2026: tenant isolation, security, database design and performance. A full app walk opened every page of every portal (platform, institution admin, teacher, student) for each of the three institutions, in a real browser, and found no crashes, failed API calls or error screens.

## Fixed in this phase

- **Secret question for platform admins.** Needed to terminate or permanently delete an institution, export an institution, download a full backup and restore a backup. Only a hash of the answer is stored; five wrong answers lock these actions for 30 minutes. Set it under **Platform → Settings**.
- **Callback secrets kept out of logs.** M-Pesa and Africa's Talking callback URLs contain a secret. Access and error logs now show `[redacted]` instead. **Rotate `MPESA_CALLBACK_SECRET` and `AT_CALLBACK_SECRET` once**, since older logs may hold them.
- **Upload quotas.** Each person may upload 200 MB per day (`STORAGE_USER_DAILY_MB`) and each institution may hold 2 GB (`STORAGE_SCHOOL_LIMIT_MB`), so one account cannot fill the shared 10 GB.
- **Reset email flooding.** Forgot-password is now limited per account (3 per hour) as well as per IP address.
- **Account recovery** can no longer target another institution admin; that would let one admin take over another's sign-in. A password reset link is still allowed.
- **Indexes** were added for the platform audit trail and for foreign keys on large tables (quiz answers, message deliveries, stored files, timetable entries).
- **Permanent deletion** removes stored files only after the database deletion has committed.

## Confirmed sound

- Every tenant query is limited to the caller's institution. Teachers reach only what they teach, students only their own records, and staff only what their permissions grant. The route-walk isolation tests cover every endpoint with an ID.
- Sessions use httpOnly cookies, CSRF tokens, session ids that can be revoked, rotating refresh tokens and single-use hashed reset codes.
- There is no raw HTML rendering, and exported spreadsheets are protected against formula injection.
- Uploads are checked by type and contents, and downloads use short signed links.
- SQL is parameterised throughout, security headers are strict, and login and other sensitive actions are rate-limited.

## Follow-ups (not urgent at current size)

| Area | Issue | When it matters |
|---|---|---|
| M-Pesa | Paybill confirmations are trusted once the callback secret matches. Set `MPESA_ALLOWED_IPS` and confirm each paybill payment with Daraja's transaction status before crediting it. | Before switching M-Pesa on |
| Performance | The academic-years page counts every mark in Python. Move the counts into SQL. | About 5,000 students |
| Performance | Fee import, year promotion, timetable copy and student import run one query per row. Batch them. | Imports above about 500 rows |
| Performance | Progression checks run per student when an offering changes. | Universities with progression on |
| Backups | Institution export stops at 200,000 rows per table. Large schools will need the full platform backup. | About 3,000 students with daily attendance |
| Data protection | M-Pesa payloads keep payer names and phone numbers indefinitely. Add a retention period and mask them. Guardian occupation is collected without a use. There is no per-student erasure for learners who have left. | Before onboarding many schools |
| Storage | Files uploaded but never attached are never cleaned up. | As usage grows |
| Sessions | Access tokens without a session id skip the revocation check. These are only legacy tokens; all current tokens carry one. | Low |

Hosting is to be decided after the full app test, as agreed.
