# Academic configuration and operational dashboards

Implemented and verified locally on 28 October 2026. These changes are in the working tree; hosted production has not been migrated or deployed.

## Changes completed, in order

1. **Platform-owned onboarding.** Creating an institution now selects an editable academic template for kindergarten, primary, high school, college, university or training. Configure group/programme structure, cohort/individual registration, term/semester/block calendar, numerical/competency/mixed assessments, credits and institution terminology. Platform institution details also have an Academic configuration editor. Existing institutions retain their records and should have their setup reviewed and saved. These are starter templates, not certified national curriculum or grading rules.
2. **Academic records behind the configuration.** Institution administrators can create and edit departments, programmes, study levels and a course catalogue. Teaching groups connect to programmes/levels; offerings connect to catalogue courses and calendar periods. Existing offerings remain cohort-based. Linked historical identities cannot be silently reassigned after assessment or completion history exists.
3. **Registration and learner outcomes.** Administrators register individual learners for offerings. Registration controls materials, assignments, subject registers and lecturer access, including delegated learner workspaces. Cohort offerings keep whole-group access. Competency assessments use saved rubric labels and numerical assessments preserve grading bands when first marked. Results remain hidden until released. Administrators can explicitly approve and release verified course completion; students see earned credits, counted once per catalogue course. Marks do not automatically award credits.
4. **Role-specific dashboards.** Platform administrators see customer attention, subscription distribution, saved payment history and audit activity. Institution administrators see register coverage, setup issues and marking work. Educators see assigned teaching groups, course registers and submitted work awaiting marking. Learners see upcoming work, released feedback and attendance. Charts use saved records, leave missing attendance days blank, exclude excused sessions from rates and offer exact-value tables. Refresh is available immediately, with automatic updates every 30 seconds.
5. **Integrity and verification.** Tenant relationships, assigned-course access, closed-year locks, stale update protection, backup round trips, grade history and learner result visibility are tested. Saved registers and outcomes add audit events. Dialogs trap keyboard focus, restore focus on close and support Escape; mobile dashboards keep wide tables inside their own scroll regions.

## Where to use it

- Platform → Institutions → Create institution → Academic setup.
- Platform → Institutions → open an institution → Academic configuration.
- Institution → Academic structure: departments, programmes, levels and catalogue.
- Institution → Teaching allocations: group programme/level and offering catalogue/period/registration.
- Institution → Course enrollment: individual registration and verified final outcomes.
- Educator → Assessments / Scores: numeric or competency marking as permitted by institution policy.
- Student → Academic record: released completion records for institutions with credits enabled.

Platform policy edits are restricted to the platform administrator by default. An explicit configuration option allows institution administrators to edit grading/label policy. All definitions and academic records remain institution-scoped. Retain the existing read-only delegation restrictions for teachers and institution administrators; platform administrators retain full delegated access.

## Verification

- Backend regression: 186 tests passed, including 22 academic configuration/integrity tests.
- Frontend regression: 31 tests passed; lint and production build passed.
- PostgreSQL migration upgrade, downgrade and schema-drift checks passed on a disposable local database; the local preview database was upgraded afterward.
- Connected browser checks use synthetic local accounts and actual React, API, PostgreSQL and Redis services. They exercise onboarding templates, configuration saving, individual registration, learner course access, released credits, competency marking and dashboard navigation. No onboarding email is sent by these checks.
- All four dashboards passed connected browser checks at desktop and 390-pixel phone widths, with no page-level horizontal overflow or browser script errors. Wide registers scroll within their own panels. Screenshots were visually reviewed.

The new migration downgrade deliberately refuses to discard populated curriculum/registration/completion records or saved grading snapshots. Review a real deployment backup and migration plan before applying these migrations to hosted data.

## Remaining product work, in priority order

1. **Pilot operations:** verify real email delivery, MFA for privileged accounts, scheduled offsite backups and restore drills, monitoring/alerts, deployment secrets and retention policies; conduct broader accessibility and load testing. Current dashboards are not load-certified for a large national customer base.
2. **Academic progression:** report cards, cumulative transcripts and institution-configured weights/final grades/GPA are implemented; see [Report cards and transcripts](ACADEMIC_REPORTS.md) and [Grading rules](GRADING_RULES.md). Institution-configured individual progression, retakes and prerequisites are implemented; see [Student progression](STUDENT_PROGRESSION.md). Per-programme policy overrides, registration windows and progression decision reversal remain separate.
3. **Daily institution workflows:** timetable/calendar coordination, guardian access and consent, notification preferences, controlled absence/leave requests and institution-specific student-fee ledgers. Platform subscription billing is separate from learner fees.
4. **Reporting and oversight:** period-specific consolidated reports, attendance interventions, exports with privacy controls, configurable approval chains and institutional acceptance testing for each supported education type.

Agree the pilot institution's policies and acceptance criteria before calling these features production-ready. Programme/catalogue support and credits are useful foundations; they do not by themselves constitute a complete university ERP.
