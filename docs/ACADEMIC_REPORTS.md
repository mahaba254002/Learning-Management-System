# Report cards and transcripts

Implemented locally on 28 October 2026. No hosted database migration or deployment was performed.

## Use the workflow

1. **Prepare the calendar and assessment periods.** In Academic years, create the institution's terms, semesters or blocks. In assessment authoring, choose Reporting term / semester. A semester-specific offering can supply the default period. Whole-year school subjects can have different assessment periods. Reports never infer a reporting term from a deadline or creation date. Older assessments without a period remain available in full-year reports and cumulative transcripts; assign a period before issuing a term-specific report.
2. **Mark and release results.** Save numeric marks or competency observations using the configured institution policy, then release the assessment results. Published assessments that are withheld or missing a learner outcome prevent issuance for their reporting scope. Unpublished drafts are excluded. A learner with no released outcomes cannot receive an empty document.
3. **Review a document.** Open Report cards & transcripts in the institution sidebar. Select a teaching group, learner, document type and reporting period. Historical enrollments remain selectable. Full-year cards include that group's recorded year; transcripts include all recorded enrollment years and attempts. Class supervisors can preview their supervised groups' report cards, while cumulative transcripts require institution administration access.
4. **Issue and release.** Institution administrators review the preview, add optional institution remarks and explicitly confirm release. The server recomputes the document and rejects changed source records. Issued documents receive a unique reference, issuer identity and fixed JSON snapshot. Duplicate issuance of the same content is rejected. Platform administrators can use their existing full-access institution workspace to issue documents as the real actor.
5. **Student access and printing.** Students see only their own active issued documents in Report cards & transcripts. Open a document and choose Print / Save as PDF, then choose the printer or PDF destination in the browser dialog. Draft previews carry a visible not-issued label. The print layout removes navigation and editing controls and supports A4 pagination. There is no public anonymous document URL.
6. **Corrections.** Revoke an incorrect document with a reason, correct the source records and issue a replacement after reviewing a new preview. If the academic content is unchanged, identify the correction in the institution remarks. Revoked documents remain visible to authorized staff, disappear from student access and cannot be printed using the app's print button. Already downloaded or printed copies cannot be recalled; verify the reference and current status with the institution.

## What each education type receives

| Institution | Report behavior |
| --- | --- |
| Kindergarten | Learning progress report with individual competency observations and feedback; no fabricated numeric marks, ranks or credits. |
| Primary | Numeric and/or competency outcomes according to platform configuration, group/year or term scope and recorded daily attendance. |
| High school | Numeric report cards, configured grade labels, teacher feedback and recorded attendance; mixed methods remain configurable. |
| College and university | Report cards and cumulative transcripts grouped by year/cohort, programme and level; catalogue codes, periods, approved completion and credits where enabled. |
| Training institution | The same configurable workflow using trainer, trainee and module terminology; competencies, numeric marks and credits follow actual configuration. |
| Other/custom | Institution labels and academic configuration control the content; no national grading or award policy is assumed. |

The assessment policy takes precedence over the starter template: for example, a custom competency-only institution receives a learning progress report regardless of its type.

## Calculation and history rules

- Numeric assessment rows show recorded marks, maxima and saved grading-band labels. A zero score is a recorded outcome. Observed numeric percentage is the sum of recorded numeric marks divided by their maxima. It is explicitly not a weighted final subject grade.
- Competency outcomes retain each assessment's recorded observation and feedback. They are not converted to numbers or averaged. Unconfigured grade bands remain blank; the product does not invent letter grades.
- Credits require a released administrator-approved course completion. Failed completion contributes zero earned credits. Passed/exempt attempts remain visible; repeated catalogue courses contribute their highest approved credit value once within the document scope.
- Daily attendance shows saved present, late, absent and excused counts. Present/late percentage excludes excused records. A missing register is not an absence, and there is no claim that all scheduled school days were recorded. Term report attendance is date-scoped to that academic period.
- Issued snapshots preserve institution identity, learner name/admission number, labels, grades, feedback, attendance, completion and remarks even if their source records later change. Issuance is allowed for closed academic years without reopening academic edits. PostgreSQL snapshot isolation keeps the issuance read consistent.
- Documents are included in the learning data set of institution backup exports and full database backups. Merge restore rejects conflicting issued content and cannot reactivate an already-revoked document. The migration refuses a downgrade that would discard issued documents or assessment period assignments.

## Verification and boundaries

The backend regression suite passes 205 tests, including 19 new report tests covering all seven institution types, term boundaries, withheld/missing outcomes, immutable snapshots, stale previews, duplicate issuance, client snapshot injection, cross-tenant access, teacher supervision, student privacy, closed years, credits, delegation, audit events and backup revocation preservation. Frontend regression has 31 passing tests; lint and production build pass.

Connected browser checks exercise institution previews and release, student document access, revocation, mobile layout, supervisor preview, assessment period editing and printed/PDF output on the real local React/API/PostgreSQL/Redis stack. Synthetic institutions cover early years, primary, college and university in these browser checks. PDF text and page layout are reviewed, including multi-page content.

Institution-approved assessment weighting, final grades and GPA are now implemented; see [Grading rules](GRADING_RULES.md). Still separate: award classifications, signatures/seals, external verification, bulk issuance, guardian delivery and national curriculum certification. Current documents are records of actual released outcomes, not an invented examination-board transcript or an automatic degree-award decision.
