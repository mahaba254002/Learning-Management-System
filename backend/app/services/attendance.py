"""How attendance records count, and percentage summaries per subject and term.

Present counts as attended. Late counts as attended unless the student arrived
within the institution's cut-off (default 30 minutes) of the lesson's end; that
counts as missed unless the teacher accepted a reason. Excused records are left
out of the percentage."""
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import func

from app.models.academic import AcademicClass, Attendance
from app.models.pilot import AcademicPeriod, AcademicYear


def outcome(status, arrived_at=None, lesson_end=None, reason_accepted=False, cutoff_minutes=30):
    if status == 'PRESENT':
        return 'ATTENDED'
    if status == 'ABSENT':
        return 'MISSED'
    if status == 'EXCUSED':
        return 'EXCUSED'
    if reason_accepted or arrived_at is None or lesson_end is None:
        return 'ATTENDED'
    today = date.today()
    minutes_left = (datetime.combine(today, lesson_end) - datetime.combine(today, arrived_at)).total_seconds() / 60
    return 'MISSED' if minutes_left <= cutoff_minutes else 'ATTENDED'


def percent(counts):
    attended, missed = counts.get('ATTENDED', 0), counts.get('MISSED', 0)
    total = attended + missed
    return dict(attended=attended, missed=missed, excused=counts.get('EXCUSED', 0),
                percent=round(attended * 100 / total, 1) if total else None)


def class_periods(db, institution_id, group):
    """Terms or semesters of the class's academic year, oldest first."""
    year = db.query(AcademicYear).filter_by(institution_id=institution_id, name=group.academic_year).first()
    if year is None:
        return None, []
    periods = db.query(AcademicPeriod).filter_by(institution_id=institution_id, year_id=year.id).order_by(AcademicPeriod.start_date).all()
    return year, periods


def date_range(db, institution_id, group, period_id=None):
    """The chosen period, else the one containing today, else the whole academic year."""
    year, periods = class_periods(db, institution_id, group)
    chosen = next((p for p in periods if p.id == period_id), None) if period_id else None
    if period_id and chosen is None:
        return None
    if chosen is None and not period_id:
        today = date.today()
        chosen = next((p for p in periods if p.start_date <= today <= p.end_date), None)
    if chosen is not None:
        start, end, label = chosen.start_date, chosen.end_date, chosen.name
    elif year is not None:
        start, end, label = year.start_date, year.end_date, year.name
    else:
        start, end, label = date.min, date.max, group.academic_year
    return dict(start=start, end=end, label=label, period_id=chosen.id if chosen else None,
                periods=[dict(id=p.id, name=p.name, start_date=p.start_date, end_date=p.end_date) for p in periods])


def counts(db, institution_id, class_ids, start, end, student_ids=None, scope_keys=None):
    """{(student_id, scope_key): {outcome: n}} for the classes and dates given."""
    q = db.query(Attendance.student_id, Attendance.scope_key, Attendance.outcome, func.count(Attendance.id)).filter(
        Attendance.institution_id == institution_id, Attendance.class_id.in_(class_ids),
        Attendance.day >= start, Attendance.day <= end)
    if student_ids is not None:
        q = q.filter(Attendance.student_id.in_(student_ids))
    if scope_keys is not None:
        q = q.filter(Attendance.scope_key.in_(scope_keys))
    result = defaultdict(dict)
    for student_id, scope_key, kind, n in q.group_by(Attendance.student_id, Attendance.scope_key, Attendance.outcome).all():
        result[(student_id, scope_key)][kind] = n
    return result


def merge(*parts):
    total = defaultdict(int)
    for part in parts:
        for key, n in part.items():
            total[key] += n
    return dict(total)


def class_of(db, institution_id, class_id):
    return db.query(AcademicClass).filter_by(institution_id=institution_id, id=class_id).first()
