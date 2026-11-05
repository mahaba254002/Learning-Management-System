# Institution management and optional learning

The same installation supports customers who need employee and academic administration, student record keeping, or online learning. Institution type (school, college, university, etc.), academic policy, enabled modules, and account permissions are separate settings.

## Packages

| Package | Includes |
| --- | --- |
| Management Only | Staff directory, departments, course catalogue and allocation, academic calendar, staff attendance |
| Management + Student Records | Management plus student records, enrollment and student attendance; no student portal or online coursework |
| Management + Learning | All implemented modules, including student access, materials, coursework, outcomes, reports and progression |

Platform administrators select a package during institution creation or change **Institution modules** on the institution details page. Individual switches allow custom combinations. The editor enables prerequisites automatically and turns dependent features off when their prerequisite is disabled. The server independently validates these relationships. Institution administrators can inspect their package but cannot change their entitlement.

Existing institutions with empty module settings retain full functionality. Selecting a package does not change institution type, academic structure, grading rules or billing. Subscription amounts remain explicitly configured by the platform administrator.

![Management dashboard with staff, department and allocation counts](images/institution-management-dashboard.png)

![Platform administrator module selection](images/institution-modules.png)

## Management workflows

1. Create departments in **Departments and faculties**. Universities can add faculties or schools and place departments under them, one level deep. Schools can keep a flat list.
2. Add every employee in **Staff directory**: staff number, department, job title, employment type, status, joining date, contact details, and optionally gender, date of birth, qualification and specialisation. This is the one staff record for everyone; the old separate teacher profile is no longer used.
3. A staff record can have a sign-in account, or none. When adding someone, choose **Create account and email a set-password link** (the link works once and expires in 72 hours), **Create account with a temporary password** (expires in 7 days and must be changed at first sign-in), or **No account**. Teaching staff get a teacher account; non-teaching staff get a staff account. An existing record can be given an account later with **Sign-in** in its row, which also resends an unused link. Teacher invitations still work and now also end with a set-password link instead of an emailed password.
4. Non-teaching staff sign in through the staff door (Teacher or staff) and see only the pages their administrator ticked under **What they can do**: view the staff directory, take staff attendance, or view student records.
5. Create courses in **Academic structure → Course catalogue**. For CBE learning areas, open **Strands** on a catalogue row to add strands and sub-strands. Assessments can then point at a strand.
6. Every offering has one lead teacher, chosen when it is created under **Classes and teaching**. Use **Teaching allocations** to add co-teachers, set groups and weekly hours, or make someone else the lead. Co-teachers have the same access to the offering as the lead. Combined weekly hours cannot exceed 168 in one academic year.
7. Use **Staff attendance** to mark a date with Present, Absent, Late, On leave or Off duty, optionally with a note. New attendance cannot precede the joining date or use a future date. A conflicting entry rejects the entire batch.

### Account states

Accounts move one step at a time, and each step can be undone:

| State | Meaning |
| --- | --- |
| Active | Can sign in |
| Suspended | Temporarily blocked |
| Deactivated | Left the institution; records kept. Needs a reason. A teacher must first hand over open offerings they lead and classes they supervise. Their co-teaching in open years is removed. |
| Archived | Hidden from lists and read-only. Needs a reason. |

Every change ends the person's sessions and is recorded in the audit trail. Nothing is permanently deleted here.

## Levels and assessment scales

At onboarding the platform administrator chooses, on the institution details page, which levels the institution offers (ECDE, lower and upper primary, junior school, senior school, college, TVET, university) and the assessment scale for each. Presets cover CBE four and eight levels, letter grades A–E, GPA 4.0 and 5.0, TVET competent / not yet competent, and percentage only. They can be copied and adjusted, or a new scale defined. The presets are starting points, not official policy; confirm the bands with the institution.

Classes, programmes, study levels and catalogue courses can be tied to a level. An assessment copies its level's scale when it is created and when its first marks are saved, so later scale changes never rewrite past results. A custom scale that marks already use cannot be edited, only copied. A level with classes or courses can be made inactive but not removed. Existing institutions were given the level their type implies and no scale, so their marking is unchanged until a scale is assigned.

Classes also have an optional stream, for example Grade 7 East.

## Student records and sign-in

Student enrollment can exist without portal access. In the class roster, administrators can create a student with **Enable student sign-in** off. When the institution's portal is disabled, new students and imports receive no sign-in access or credentials. Internally, the existing user identity continues to anchor names and academic history; its `login_enabled` flag blocks authentication and refresh.

Enabling a package later does not automatically enable those records. An administrator explicitly enables each student's sign-in, assigns the login identity and resets their password to issue credentials. Disabling individual sign-in revokes practical access immediately; disabled users cannot be opened through delegated workspaces. Changing student identities also invalidates earlier sessions.

Disabling the institution's student portal blocks existing student sessions and refreshes. Account logout and password/security endpoints remain available where the account itself remains enabled. Imports must be previewed again if portal availability changes between review and commit.

## Enforcement and preservation

- Modules apply to the institution; role, tenant membership and existing teaching/enrollment relationships still control each action.
- Navigation, direct page access, dashboard links and API routes follow module availability. Checks run for delegated workspaces too.
- Configuration and security endpoints remain accessible so administrators can inspect the package and manage accounts.
- Turning off a module preserves its records. Turning it back on restores access to the same records.
- Updates require the version loaded by the editor. Concurrent changes return a conflict instead of overwriting another administrator's work.
- Employee, department, allocation, attendance, account, permission, level, scale and strand changes are audited. Institution backups include staff records, levels, strands and teaching allocations. Restoring an older backup turns its teacher profiles into staff records.

## Upgrade and validation

Revision `k3a4b5c6d7e8` added module settings and the management tables. Revision `m5c6d7e8f9a0` adds levels, scales, faculties, strands, staff accounts and co-teaching. It copies each teacher profile into a staff record and gives every offering a lead-teacher row. It stops before changing anything if old course allocations exist. Downgrade refuses while staff accounts, closed accounts, co-teachers or linked non-teaching staff exist, and recreates teacher profiles for teachers added after the upgrade. The old teachers table stays in place, unused, for one release.

HTTP tests in `backend/tests/test_management.py` and `backend/tests/test_structure_and_staff.py` cover presets, dependencies, authorization, tenant boundaries, delegated access, session restrictions, employee updates, allocations, workload limits, atomic attendance, record-only student creation and backup recovery. Frontend tests cover package navigation and dependency changes. Validate the migration on an isolated PostgreSQL database before deployment.

This implementation does not include payroll, employee self-service, leave approval workflows or timetable conflict detection. Staff permissions are a fixed list of three. Staff records and a leave attendance status do not imply those workflows exist.
