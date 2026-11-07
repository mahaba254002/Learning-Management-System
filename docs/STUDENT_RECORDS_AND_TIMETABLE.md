# Student records and timetables

This covers roadmap phases 5 and 6. Migrations: `o7e8f9a0b1c2` (student records and the attendance late rule), then `p8f9a0b1c2d3` (timetables). Both run after the M-Pesa migration `n6d7e8f9a0b1`. Their downgrades refuse once the new tables hold records.

## Student records

Institution → **Student records** lists students by status, class or search. Opening a student shows their status, guardians, fee standing by term and discipline records.

| Who | Sees | Changes |
| --- | --- | --- |
| Institution administrator | Everything | Status, guardians, fees, discipline, announcements |
| Class teacher (class supervisor) | Students in classes they supervise: guardians, fees, discipline | Discipline records they wrote |
| Staff with *View student records* | Student list, details and guardians | Nothing |
| Staff with *View and update student fee status* (new `fees.manage` right) | Fee status | Fee status and fee list uploads |
| Subject teachers and students | No access | — |

**Status.** A student can be Active, Transferred, Graduated or Withdrawn, with the date they left and a note. Leaving takes them out of their current classes; marks, attendance and reports stay. Transferred and withdrawn students can no longer sign in. Graduates keep sign-in so they can view their records. Returning a student to Active restores sign-in, but class places must be given again. A student who has left cannot be enrolled until returned to Active.

**Guardians.** Name, phone, relationship, optional email and occupation. The phone is stored in international form (`0712 345 678` becomes `+254712345678`). Adding a guardian whose phone is already on record links the existing person, so siblings share one guardian. One guardian per student is the main contact. Removing a guardian from their last child deletes the guardian.

**Fee status.** Fees are collected in the institution's own system. Skynet records, per student and term or semester: Paid, Partly paid or Not paid, the balance in KES and a note. Paid always has a zero balance and Partly paid must have a balance above zero. A CSV from the fees system (`admission_number`, `status`, `balance`, `note`) is checked row by row first and applied only when every row is valid. Admission numbers match regardless of case. Every change is audited.

**Discipline.** Date, category, what happened and action taken. Students and their guardians do not see these.

**Announcements.** The administrator posts to everyone, staff and teachers, all students, or one class. Class announcements reach that class's students, its class teacher and the teachers who teach it. An optional end date hides a notice afterwards.

## Attendance percentages and the late rule

Present counts as attended. For a late student the teacher records the arrival time. On a subject register with a lesson end time, a late arrival counts as absent if it falls within the institution's cut-off before the lesson ends, unless the teacher ticks *Reason accepted* and writes the reason in the note. Excused sessions are left out of the percentage.

The cut-off is under Settings → Learning configuration (*Late arrival cut-off*, default 30 minutes, 0 to 240). Arriving exactly at the cut-off counts as absent. How each record counts is fixed when it is saved, so changing the cut-off does not rewrite past registers. Records from before this release have no arrival times, so their late entries stay attended.

Percentages are per student for a class, per subject and for the daily class register, over a term or semester (the current one by default, or the whole academic year when no terms exist). Class teachers see every column; subject teachers see their subjects. Students see their own rates on *My attendance*. Below 75% is highlighted on screen; nothing else depends on that figure.

## Timetables

Institution → **Timetable**, per term or semester. Nothing is generated or imported. The administrator fills it in, usually after the staff meeting that agrees it.

1. **Bell schedule.** Set the teaching days and the periods: lessons and breaks with start and end times. A period can be limited to certain days (for example a shorter Friday). Periods cannot overlap on the same day.
2. **Teacher availability.** Weekly times a teacher cannot teach, for example part-time days. Adding a time lists lessons already placed in it.
3. **Lessons.** Choose a class and add a lesson to a cell: the subject and, when it has co-teachers, which teacher. A lesson is refused when the teacher is already teaching, the class already has a lesson (two optional offerings may share a period, for electives), or the teacher is unavailable. The administrator can save anyway with a reason. The reason shows on the lesson and goes to the audit trail.
4. **Publish.** Teachers and students see a term's timetable only once it is published. Unpublishing hides it again.
5. **One-day changes.** From a lesson: cancel it, move it to another date and period, or have another teacher cover it, on one date. Moves and covers are checked for clashes on that date in the same way.

*Copy timetable* starts an empty term from another term's bell schedule and lessons, skipping offerings that do not run in the new term.

Once published:

- Teachers get **My timetable**: their week, with cancelled, moved and covered lessons marked, and lessons they cover for others. *Take attendance* on a lesson opens that subject's register for the date with the lesson end time filled in for the late rule.
- Teachers and students see **Today's lessons** on their dashboard.
- Students get **Timetable**: their week and their class grid, showing only the optional subjects they are registered for.

Rooms and printing are not included.
