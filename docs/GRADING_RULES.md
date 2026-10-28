# Institution grading weights, final grades and GPA

Implemented locally on 28 October 2026. Hosted production has not been migrated or deployed. No national grading scale is assumed.

## Configure an institution

Platform → Institutions → open an institution → Academic configuration → **Final grades, assessment weights & GPA**. The same editor is available during onboarding. All institution types start with numeric final grading and GPA disabled; platform admin enables and enters the customer's approved rules explicitly.

Choose:

- A policy name/version.
- Total numeric points divided by total maxima, or category weights for ASSIGNMENT, COURSEWORK and EXAM. Weighted categories must total exactly 100%. A category with zero weight is excluded from the numeric final calculation.
- Within a category, pooled points or equal assessment percentages.
- Pass threshold, final grade bands (including zero), percentage decimal places, half-up/half-even/truncate rounding, and whether thresholds use the raw or rounded percentage.
- Optional GPA scheme name, scale, grade points for every band, GPA decimal places and repeat-course rule: all attempts, latest academic offering, or best grade points. Failures count according to that repeat rule. Grade points cannot decrease as marks increase.

GPA requires credits enabled and a linked catalogue course with positive credits. Competency-only institutions cannot enable numeric finals or GPA. A kindergarten can retain observations alone; a primary school can use numeric/mixed final grades without GPA; a college, university or training provider can enable GPA. Institution type does not impose a national curriculum or an invented grade scale. Custom institutions use the same explicit configuration.

Institution administrators cannot change these final-grading/GPA rules, even if terminology and individual-assessment grade-label editing is enabled for them.

## Mark, review and release

1. Educators create assessments, select their category and reporting period, save marks and release assessment results.
2. In Assessment outcomes / Scores, select an offering. **Final grades & approval** shows the full-offering or selected-period calculation, weighted category contributions and missing requirements. Class rosters are batched in the database instead of repeating the shared queries for each learner.
3. Missing marks, withheld contributing results and missing positive-weight categories block final approval. They do not become zero and their weights are not redistributed. Recorded zero marks count. Competency assessments remain separate and never become numeric grade points.
4. Institution administrators approve and release each reviewed result. Teachers see calculations for assigned courses but cannot approve them. Read-only delegated workspaces cannot release grades; platform admins can approve through their existing full-access institution workspace.
5. Full-offering approval updates linked course completion to PASSED or FAILED and releases it with catalogue credits. Period sub-results do not award course credits or contribute to GPA. Exempt completion records require resolution before numeric final approval; exemptions earn approved credits where appropriate but are excluded from GPA.
6. Students see current released final grades in Outcomes & feedback, with GPA where enabled. Academic record shows released completion and deduplicated earned credits. Reports and transcripts include approved final percentages, grade labels, points, policy name and category contributions. Issuance is blocked when required final approval is missing or stale.

## GPA arithmetic and repeats

GPA is the sum of `(grade points × attempted credits)` divided by attempted credits. Failed attempts contribute attempted credits and their configured points. Earned credits remain a separate measure: repeated catalogue courses earn credits once, while GPA follows the configured repeat rule.

Only current released full-offering results contribute. Exemptions and term sub-results are excluded. Latest attempt uses academic period/year start and then offering creation order; approving an older attempt later does not make it the latest academic attempt. BEST selects the highest grade points, breaking ties by the later offering.

Different scheme names, scales, repeat rules, GPA precision or rounding are shown separately; the system does not average incompatible GPAs. Arithmetic uses Decimal values. Grade/pass classification uses the selected raw/rounded basis, not an accidentally rounded display value.

## Policy history and corrections

At the first final approval, the offering pins its complete policy. Subsequent platform policy changes do not reinterpret that offering. New or unpinned offerings use the currently saved institution policy. Approved results retain their policy and calculation; issued academic documents retain fixed snapshots.

To intentionally recalculate an existing offering, platform admin opens **Apply revised grading rules to an existing offering** below the institution configuration, searches/selects the offering and types its exact name. The action applies the saved institution policy, withholds all affected final grades and non-exempt completion records, and records an audit event. Institution admin must review and release results again. Closed years remain locked. Already-issued incorrect documents must be revoked separately; applying rules does not rewrite them.

Changes to published assessments, contributing marks, release status, categories or credits can invalidate an approved result. Stale results and derived credits are excluded from the student record/GPA until reapproval, and new report issuance is blocked. Staff can refresh the calculation and review again. Withholding a full-offering final grade also withholds its linked non-exempt completion record. Manual completion changes are blocked while a full-offering final grade is released.

Final results and pinned policies are included in institution learning backups and full database backups. The migration refuses to discard populated final-grade records on downgrade. Existing issued reports remain readable with their older schema and do not gain invented retroactive GPA values.

## Verification

- Backend regression: 250 tests, including 45 grading tests for arithmetic, boundaries, incomplete marks, zero marks, weights, every institution type, policy ownership, grade history, credits, repeats, failures, exemptions, stale approvals, tenant/role boundaries, read-only delegation, closed years, backups, policy revision and batched roster queries.
- Frontend regression: 31 passing tests; lint and production build pass.
- Isolated PostgreSQL upgrade, downgrade and schema-drift checks pass; local preview upgraded afterward. Hosted data untouched.
- Browser checks cover real platform configuration, primary final grades, college/university GPA, withholding/release, teacher permissions, explicit policy revision, student mobile views and transcript issuance. Kindergarten remains competency-only. Issued PDF output was rendered and visually reviewed.

Still separate: programme-specific policies within one institution, custom assessment categories beyond the three supported types, minimum-exam or other hurdle rules, dropped assessments, grade appeals/approval chains, award classifications and examination-board certification. Use a new policy version and explicit review rather than treating these unsupported rules as implicit calculations.
