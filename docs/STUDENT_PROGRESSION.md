# Student progression, retakes and prerequisites

## Platform setup

Open **Platform → Institutions → customer → Academic configuration → Progression, retakes & prerequisites**. The same configuration is available when onboarding a new institution. Every institution type supports its own rules; progression starts disabled. These are customer-defined rules, not statutory Kenyan promotion criteria.

Configure advancement/completion thresholds using passed courses, failed courses, source-group credits, cumulative GPA, recorded attendance and/or accepted competency labels. GPA requires enabled numeric final grading and credits; its threshold cannot exceed the configured scale. Kindergarten and other competency programmes can use released observations without numeric grades or GPA. All published competency observations in an offering must meet one of the selected labels. Competency completion awards zero credits; credit awards require verified course completion or approved numeric final grades.

Use **Course prerequisites** below the academic setup to choose a catalogue course and up to 20 required courses. All selected courses are required. Self-links, duplicate links, cycles and links to another institution are rejected. An optional final percentage accepts up to four decimal places and requires a current, released numeric final grade. Manual pass records and competency observations have no numeric percentage. Released exemptions can satisfy prerequisites when the policy permits them, including percentage requirements.

Retake configuration controls whether another attempt is allowed, the total maximum attempts including the first, repeating a passed/exempted course, and whether earlier attempts must be complete and released. Attempts follow catalogue identity across offerings and academic years. Historical cohort enrollments and individual registrations—including inactive/cancelled registrations—count as attempts. Cancelled registrations do not erase failed or unfinished progression outcomes. A reactivation of the same offering remains the same attempt.

## Institution workflow

1. Configure source and destination academic years, programmes and study levels. Close the source year unless platform policy explicitly allows open-source review. Same-year advancement requires open-source review and same-year level advancement enabled.
2. Publish, assess and release outcomes. Numeric final grades must be approved and current. Unreleased or changed grades do not satisfy eligibility. Manual verified course outcomes and allowed competency observations also contribute.
3. Open **Student progression**, choose the source group, learner and **Advance**, **Repeat level**, or **Complete programme / level**. Choose a destination for advancement/repetition.
4. Check eligibility. Review the recorded metrics and blockers. Advancement moves to a higher configured level; repetition retains the same level. Destination programmes must match. Destination years must be later and open, except explicitly allowed same-year advancement.
5. Confirm the review and approve. If platform policy permits overrides, academic threshold failures require a reason of at least ten characters. Structural issues, prerequisite checks and retake entry restrictions cannot be overridden.

Repetition skips advancement/completion academic thresholds but still checks destination structure and course entry requirements. Passed, failed and incomplete counts refer to source teaching offerings, including recorded repeat attempts. Credits are deduplicated by catalogue identity within the source group. GPA is cumulative and requires one compatible grading scheme. Attendance uses saved daily class registers, counts present and late, and excludes excused days; missing attendance cannot satisfy a threshold. An empty/unregistered source course list cannot satisfy the all-completed rule.

Approval rechecks eligibility against the preview, rejects stale reviews and duplicate decisions, and adds/reactivates destination enrollment. It preserves source enrollment, scores, attendance, course completions, final grades and issued documents. Individual course registrations in the destination are handled separately by Course enrollment and checked at registration.

There is one final decision per source enrollment. This version has no decision reversal screen; carefully review before approving. Saved decisions retain a policy/metric snapshot and optional override reason. Administrators can inspect the latest 50 decisions. Students see their own decisions under **My progression**, without internal override reasons. Teachers cannot approve; existing read-only student workspace access remains available.

## Enrollment safeguards

Ordinary enrollment cannot move an existing learner across years or levels while progression is enabled; use the reviewed workflow. New admissions remain possible, subject to cohort-course entry rules. Student imports check the same cohort prerequisites before preview and again at commit. Creating or reassigning offerings also checks existing enrolled/registered learners. Individual course registration enforces prerequisites and retake limits, with visible blockers in the enrollment table. Already registered learners are not automatically removed when a policy changes.

Legacy whole-year bulk promotion is unavailable while individual progression is enabled, so it cannot bypass learner-specific checks. Policy and entry writes serialize per institution, and entry checks lock configured academic years consistently with progression approval. Academic writers already lock their configured academic year.

## Recovery and validation

Signed institution backups include prerequisite links, progression decisions and academic configuration. Restore refuses to overwrite a different existing progression decision. The migration refuses downgrade if progression records or prerequisite links exist, protecting history.

The local QA preview uses synthetic institutions only. Hosted databases have not been migrated or changed. Automated coverage includes role/tenant restrictions, released/stale results, competency completion, GPA/credits/attendance, overrides, duplicate decisions, prerequisites, retakes, imports, enrollment bypasses, source history and signed backup round trips. Browser checks cover kindergarten, primary, college and university workflows and mobile layouts. These checks do not constitute production load testing.
