# Administrator workspaces

Institution administrators now have a live institution overview, a searchable student directory and user-access directory, contact settings, academic oversight pages (attendance, materials, coursework and scores), their account/security page, and a scoped administrative audit trail. Existing invitation review, teacher details, class setup, and enrollment remain available.

Platform administrators have institution totals including suspended institutions, account search/filter/pagination, institution suspension/reactivation, email-verified archival, institution-admin provisioning, usage totals, account/security information and cross-institution administrative audit events. The former Revenue placeholder redirects to usage: billing, subscriptions and payment reporting are not implemented and no revenue is fabricated.

## Permissions and behavior

- Institution identity always comes from authentication. Institution administrators cannot read or change other institutions' users or academic records.
- Institution administrators can suspend/reactivate teachers and students, but cannot disable peer administrators or themselves. Platform users can manage institution accounts, but platform-admin accounts are protected from these controls.
- Suspension preserves records. Both suspension and reactivation invalidate prior sessions, including all institution sessions when institution status changes. Archived institutions remain inaccessible; archive restoration is not exposed by these controls.
- Admin creation requires a valid email and returns one-time credentials with Cache-Control: no-store. New admins must change their temporary password. No credentials are included in audit records.
- Audit logging starts at deployment. It covers institution creation, archival, status and settings changes; admin creation; user access changes; invitation sending/review; class and subject setup. It is not a historical backfill or a complete log of every academic edit, sign-in or read. The application exposes no audit-edit/delete endpoint.
- User and audit lists are paginated (50 per page, API maximum 100). User search treats wildcard characters literally.
- Browser query caches are cleared on login/logout/password change to prevent prior account data appearing in a later session.

## Deployment

Apply migration b4d5e6f7a8c9 after a3c4d5e6f7b8 before deploying this backend. It adds audit_events only. Deploy frontend and backend together. Production changes are not performed by the implementation task.

The validation script now targets this audit migration. Its disposable mode upgrades, rolls back and upgrades again, deleting test audit events during rollback. Never run disposable mode on production. It verifies model/schema agreement and preserves pre-existing academic and account row counts. Earlier teacher/student validation history remains documented in their handover files.

## Checks

Backend HTTP tests cover tenant boundaries, role restrictions, search/pagination, immutable identity inputs, suspension/reactivation and old-session rejection, CSRF, forced password changes, audit scope, academic oversight, and duplicate route registrations. Provisioning and archive service tests mock email verification; no real email is sent. Frontend checks include build, lint and the existing routing/student calculation tests. Production and email delivery are not verified by these tests.

Final validation on September 30, 2026: 55 backend tests passed; 15 frontend tests passed; production frontend build and lint passed. The audit migration upgrade, rollback and re-upgrade passed on the isolated Neon branch, with all ten academic/administration table schemas verified and existing account/academic row counts preserved. Browser interaction testing of these new admin pages was not completed. No production migration or deployment was performed.
