# Marks, grading and marksheets

Roadmap phase 7. Skynet does not design report cards. Institutions upload marks, download marksheets in Excel and produce reports in their own format. Migration: `q9a0b1c2d3e4` (after `p8f9a0b1c2d3`).

## Each institution's own grading

Institution → **Grading** sets the grade bands (from %, label, optional points), how a term mark is worked out (weighted coursework, exam and assignment, or all marks added together), the pass mark, rounding and, for credit-based institutions, GPA.

- The institution administrator can save grading **once**. After that it is locked.
- A later change is a **change request** with a reason. Only one can wait at a time, and it can be withdrawn.
- The platform administrator sees requests under Platform → **Grading requests**, compares the current and proposed grading, and approves or rejects (a rejection needs a note). Approval applies the new grading at once.
- The platform administrator can still edit an institution's grading directly in its academic setup, and can let an institution set it again (`POST /api/platform/institutions/{id}/grading-unlock`; there is no button for this yet).
- An offering keeps the grading it had when its first final grade was approved, so approved results are not rewritten.

Grade points are optional unless GPA is on. When the bands carry points, marksheets average them for the mean grade, for example a 12-point scale from A (12) to E (1).

## Uploading marks

Excel (`.xlsx`) and CSV are accepted, up to 3 MB and 3,000 rows. Formulas in an upload are never run: the value Excel last saved is used. Every upload is checked first, and nothing is saved until every row is valid. Saving never releases results to students.

**One assessment** (subject teachers, and the admin): choose the subject and assessment under **Marks & marksheets**, download the blank list if needed, and upload a file with `admission_number`, `mark` and optional `feedback`. Competency assessments take the outcome label instead of a number. Blank marks are skipped. Re-uploading the same marks changes nothing.

**Whole class, one exam** (the admin and the class teacher): name the exam (for example *End of term exam*), choose its type and what it is out of, and upload a file with `admission_number` and one column per subject, headed with the subject's name in Skynet. Columns that are not subjects (name, total, mean) are ignored. Blank cells, `-` and `ABS` mean no mark. When a subject already has an assessment with that name in the term, marks go into it. Otherwise one is created, published and out of the given maximum. Students who don't take a subject (for example an optional subject) can't receive a mark in it.

## Marksheets

Under **Marks & marksheets**, the admin and class teachers see a class marksheet for a term. They can choose:

- **Term result**: the institution's grading rule applied to every mark entered so far, whether or not results are released. A subject missing a required mark is left blank. Without a grading rule, all the term's marks are added up as a percentage.
- **One exam by name**: each subject's mark as a percentage of that exam's maximum.

Each student row shows subject percentages and grades, total, mean percentage, mean points, mean grade and position. **Mean grade** comes from the mean points rounded to the nearest band when the bands carry points; otherwise from the mean percentage. **Position** is by mean points when available, with mean percentage breaking ties; otherwise by mean percentage. Equal results share a position (1, 1, 3).

**Download Excel** gives one workbook:

1. The marksheet
2. One sheet per subject with every assessment's raw marks, the subject percentage and grade
3. *Subject analysis*: students with marks, mean, mean grade, highest, lowest and how many students got each grade

Text that a spreadsheet would read as a formula (for example a name starting with `=`) is written as plain text. Downloads are recorded in the audit trail. Subject teachers can download their own subject's marks (positions are within that subject) but not the whole class.

## Report cards and transcripts

Report cards and transcripts are switched **off** by default and hidden from menus. Nothing was deleted. The platform administrator can switch them on for an institution under its modules (*Academic reports*). The class marks overview for class teachers is not affected.
