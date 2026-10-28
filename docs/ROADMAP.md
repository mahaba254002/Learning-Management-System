# Prioritised improvement backlog

28 October 2026. This is a repository-based engineering assessment; production configuration, institutional acceptance and load capability have not been certified. Completed features are described in their feature guides and must not be reimplemented as missing work.

| Priority | Work | Where to start | Completion evidence |
| --- | --- | --- | --- |
| P0 before live upgrade | Release inventory, staging rehearsal from actual live schema, encrypted backup and recovery drill, controlled migration/release window | DEPLOYMENT.md; render.yaml; alembic; backups service | Known live commit/revision, recovery time measured, smoke checklist signed |
| P0 before pilot | Real invitation/password recovery/contact/billing email verification | auth/invitations/contact routes; email service; billing_reminders.py | Controlled mailbox receives each workflow, failure handling verified |
| P0 before pilot | Monitoring and actionable alerts; database-aware readiness check distinct from current shallow health | main.py; security_headers.py; hosting logs | API/DB/Redis/email failures detected without leaking student data |
| P0 before pilot | Privileged MFA, session/device oversight and recovery policy | auth.py; security.py; AuthContext | MFA and audited recovery tests for platform/institution administrators |
| P0 before pilot | Scheduled encrypted offsite backups, retention, access policy and repeat restore drills | services/backups.py; platform backup UI | Recoverable copy outside running system; retained signing key; recovery objectives agreed |
| P0 before pilot | Accessibility and real institutional acceptance for each supported type | layouts, forms, dialogs, registers, reports | Keyboard/screen-reader checks, contrast/zoom/error focus, agreed school/college scenarios |
| P1 commercial readiness | Portable connected browser fixtures/tests and automated CI with PostgreSQL migrations | backend/tests; frontend/tests; scripts | Clean checkout reproducibly runs tests; no reliance on ignored local QA scripts |
| P1 commercial readiness | Workload and concurrency measurements, query batching, pagination and background exports | dashboards, progression checks, registrations, backups | Representative tenant sizes meet agreed latency; concurrent writes preserve integrity |
| P1 academic operations | Audited reversal/correction workflow for final progression decisions | progression model/service/route and UI | Reversal retains original decision and handles destination activity safely |
| P1 academic operations | Programme-specific policies, registration windows and conditional enrollment workflows | academic_configuration, curriculum, progression | Platform-controlled rules tested across institution/programme boundaries |
| P1 academic operations | Reporting approval chains, consolidated period reports, controlled exports and verification workflow | academic_documents/final_grades | Institutional sign-off, reproducible snapshots and export access limits |
| P1 daily use | Timetable, calendar and absence/leave workflows | curriculum, teaching, attendance | Clash checks and permission/notification tests |
| P1 daily use | Notifications and delivery preferences | subscriptions/billing notices as existing reference | Tenant-scoped delivery, opt-outs where applicable, retries and visibility |
| P1 daily use | Secure file uploads and scanning/limits | learning routes/models, submission UI | Private scoped access, type/size limits, lifecycle and recovery tests |
| P2 expansion | Guardian portal, appropriate consent and privacy retention workflows | user/relationship models, role routes | Explicit guardian-child authorization and institution-approved data policy |
| P2 expansion | Student fee ledgers and M-Pesa reconciliation | new fee module; existing subscriptions remain platform billing | Separate institution/student ledgers, audited reconciliation and duplicate-payment protection |
| P2 expansion | Discussions, quizzes, offline workflows and advanced analytics | learning modules and dashboards | Agreed requirements, access/performance tests and user acceptance |

Implemented foundations: configurable institution structure and terminology, session renewal and private drafts, reviewed student imports, academic calendars, individual course registration, competency observations, report cards/transcripts, numeric final grading/GPA, progression/retakes/prerequisites, manual platform subscriptions/freezes, audit filtering, delegated read-only workspaces, signed backup and reviewed restore. Implemented does not mean deployed or load-certified.

Suggested sequence: P0 release/recovery and email → monitoring/MFA/accessibility → pilot with one consenting institution → progression corrections/CI/performance → daily-use modules → expansion. Record owner, target date, dependencies and acceptance evidence for each selected item in OPERATIONS_RECORDS.md. Decide retention and privacy requirements with the institution and qualified local advice; this backlog is not a legal compliance determination.
