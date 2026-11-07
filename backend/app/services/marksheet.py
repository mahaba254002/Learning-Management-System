"""Class marksheets for a term or one exam, using each institution's own grading.

Subject mark:
- One exam: the mark as a percentage of that exam's maximum.
- Term: the institution's final-grade rule (category weights, pass mark) when it is
  switched on, using every mark entered so far whether or not results are released.
  Without a rule, all the term's marks added up as a percentage.
Grades and points come from the grade bands. Mean grade comes from the mean points
when the bands carry points (rounded to the nearest band), otherwise from the mean
percentage. Position is by mean points when available (mean percentage breaks ties),
otherwise mean percentage; equal results share a position."""
from decimal import ROUND_HALF_UP, Decimal

from app.models.academic import AcademicClass, Coursework, Enrollment, Score, Student, Subject
from app.models.institution import Institution
from app.models.pilot import AcademicPeriod
from app.models.user import User
from app.services.final_grades import policy_for
from app.services.grading_rules import calculate
from app.services.learning_settings import learning_settings

TWO = Decimal('0.01')


def pct(value):
    return value.quantize(TWO, rounding=ROUND_HALF_UP) if value is not None else None


def bands_for(policy, fallback):
    bands = policy.get('bands') or fallback or []
    return sorted(({'minimum': Decimal(str(b['minimum'])), 'label': b['label'],
                    'points': Decimal(str(b['points'])) if b.get('points') is not None else None} for b in bands),
                  key=lambda b: b['minimum'], reverse=True)


def band_for(bands, percentage):
    if percentage is None or not bands:
        return None
    return next((b for b in bands if percentage >= b['minimum']), bands[-1])


def grade_from_points(bands, points):
    with_points = [b for b in bands if b['points'] is not None]
    if points is None or not with_points:
        return None
    target = points.quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return min(with_points, key=lambda b: (abs(b['points'] - target), -b['points']))


def in_period(work, subject, period_id):
    return (work.period_id or subject.period_id) == period_id


def build(db, institution_id, class_id, period_id, exam_title=None, subject_ids=None):
    institution = db.get(Institution, institution_id)
    group = db.query(AcademicClass).filter_by(institution_id=institution_id, id=class_id).one()
    period = db.query(AcademicPeriod).filter_by(institution_id=institution_id, id=period_id).one()
    fallback = learning_settings(institution)['grade_bands']
    subjects = db.query(Subject).filter(Subject.institution_id == institution_id, Subject.class_id == class_id).order_by(Subject.name).all()
    subjects = [s for s in subjects if (not s.period_id or s.period_id == period_id) and (subject_ids is None or s.id in subject_ids)]
    roster = db.query(Student, User).join(Enrollment, Enrollment.student_id == Student.id).join(User, User.id == Student.user_id).filter(
        Enrollment.institution_id == institution_id, Enrollment.class_id == class_id, Enrollment.active.is_(True),
        User.institution_id == institution_id).order_by(User.first_name, User.last_name).all()
    works = {s.id: [] for s in subjects}
    titles = set()
    for w in db.query(Coursework).filter(Coursework.institution_id == institution_id, Coursework.subject_id.in_(list(works) or [None]),
                                         Coursework.published.is_(True), Coursework.assessment_mode == 'NUMERIC').order_by(Coursework.created_at).all():
        subject = next(s for s in subjects if s.id == w.subject_id)
        if in_period(w, subject, period_id):
            titles.add(w.title.strip())
            if exam_title is None or w.title.strip().lower() == exam_title.strip().lower():
                works[w.subject_id].append(w)
    work_ids = [w.id for rows in works.values() for w in rows]
    marks = {}
    if work_ids and roster:
        for row in db.query(Score).filter(Score.institution_id == institution_id, Score.coursework_id.in_(work_ids),
                                          Score.student_id.in_([s.id for s, _ in roster])).all():
            if row.score is not None:
                marks[(row.student_id, row.coursework_id)] = row.score

    policies = {s.id: policy_for(db, s) for s in subjects}
    subject_bands = {s.id: bands_for(policies[s.id], fallback) for s in subjects}
    # Mean grade uses the institution's own bands, not a single subject's.
    from app.services.academic_configuration import academic_configuration
    overall_bands = bands_for(academic_configuration(institution)['grading_rules'], fallback)
    rows = []
    for student, user in roster:
        cells = {}
        for s in subjects:
            policy, items = policies[s.id], works[s.id]
            percentage, note = None, ''
            if not items:
                note = 'No assessment'
            elif exam_title is not None:
                w = items[0]
                score = marks.get((student.id, w.id))
                percentage = score / w.max_score * 100 if score is not None else None
                note = '' if score is not None else 'No mark'
            elif policy.get('enabled'):
                result = calculate(policy, [dict(id=str(w.id), title=w.title, kind=w.kind, maximum=str(w.max_score), released=True,
                                                 score=str(marks[(student.id, w.id)]) if (student.id, w.id) in marks else None) for w in items])
                if result['ready']:
                    percentage = Decimal(result['result']['raw_percentage'])
                else:
                    note = 'Missing marks'
            else:
                have = [w for w in items if (student.id, w.id) in marks]
                if have:
                    percentage = sum(marks[(student.id, w.id)] for w in have) / sum(w.max_score for w in have) * 100
                    if len(have) < len(items):
                        note = 'Some marks missing'
                else:
                    note = 'No mark'
            band = band_for(subject_bands[s.id], percentage)
            cells[str(s.id)] = dict(percent=pct(percentage), grade=band['label'] if band else None,
                                    points=band['points'] if band else None, note=note,
                                    marks={str(w.id): marks.get((student.id, w.id)) for w in items})
        scored = [c for c in cells.values() if c['percent'] is not None]
        total = sum((c['percent'] for c in scored), Decimal(0)) if scored else None
        mean = pct(total / len(scored)) if scored else None
        points = [c['points'] for c in scored]
        mean_points = pct(sum(points) / len(points)) if scored and all(p is not None for p in points) else None
        grade = grade_from_points(overall_bands, mean_points) if mean_points is not None else band_for(overall_bands, mean)
        rows.append(dict(student_id=student.id, admission_number=student.admission_number, name=f'{user.first_name} {user.last_name}',
                         cells=cells, subjects_sat=len(scored), total=pct(total), mean=mean, mean_points=mean_points,
                         mean_grade=grade['label'] if grade else None, position=None))

    use_points = any(r['mean_points'] is not None for r in rows) and all(r['mean_points'] is not None for r in rows if r['mean'] is not None)
    # Mean points decide first when grades carry points; mean percentage breaks ties.
    rank_key = (lambda r: (r['mean_points'], r['mean'])) if use_points else (lambda r: (r['mean'],))
    ranked = sorted((r for r in rows if r['mean'] is not None), key=rank_key, reverse=True)
    previous, position = None, 0
    for index, r in enumerate(ranked, start=1):
        key = rank_key(r)
        if key != previous:
            position, previous = index, key
        r['position'] = position
    rows.sort(key=lambda r: (r['position'] is None, r['position'] or 0, r['name']))

    analysis = []
    for s in subjects:
        values = [r['cells'][str(s.id)] for r in rows if r['cells'][str(s.id)]['percent'] is not None]
        percents = [v['percent'] for v in values]
        mean = pct(sum(percents) / len(percents)) if percents else None
        band = band_for(subject_bands[s.id], mean)
        counts = {}
        for v in values:
            if v['grade']:
                counts[v['grade']] = counts.get(v['grade'], 0) + 1
        analysis.append(dict(subject_id=s.id, subject=s.name, entries=len(values), mean=mean, highest=max(percents) if percents else None,
                             lowest=min(percents) if percents else None, mean_grade=band['label'] if band else None, grades=counts))
    grade_labels = []
    for s in subjects:
        for b in subject_bands[s.id]:
            if b['label'] not in grade_labels:
                grade_labels.append(b['label'])
    return dict(class_id=group.id, class_name=f"{group.name}{' ' + group.stream if group.stream else ''}", academic_year=group.academic_year,
                period_id=period.id, period_name=period.name, basis='EXAM' if exam_title else 'TERM', exam_title=exam_title,
                ranked_by='MEAN_POINTS' if use_points else 'MEAN_PERCENT', exam_titles=sorted(titles, key=str.lower),
                subjects=[dict(id=s.id, name=s.name, assessments=[dict(id=w.id, title=w.title, kind=w.kind, max_score=w.max_score) for w in works[s.id]])
                          for s in subjects],
                rows=rows, analysis=analysis, grade_labels=grade_labels)


def number(value):
    return float(value) if value is not None else None


def workbook(sheet):
    """Marksheet, one sheet per subject with each assessment, and a subject analysis sheet."""
    from app.services.spreadsheet import workbook_bytes
    subjects = sheet['subjects']
    head = ['Position', 'Admission number', 'Name']
    for s in subjects:
        head += [f"{s['name']} %", f"{s['name']} grade"]
    head += ['Subjects', 'Total', 'Mean %', 'Mean points', 'Mean grade']
    body = [head]
    for r in sheet['rows']:
        line = [r['position'], r['admission_number'], r['name']]
        for s in subjects:
            c = r['cells'][str(s['id'])]
            line += [number(c['percent']), c['grade'] or c['note'] or None]
        line += [r['subjects_sat'], number(r['total']), number(r['mean']), number(r['mean_points']), r['mean_grade']]
        body.append(line)
    title = f"{sheet['class_name']} {sheet['period_name']}" + (f" {sheet['exam_title']}" if sheet['exam_title'] else '')
    sheets = [(title, body, [10, 18, 28] + [12, 10] * len(subjects) + [10, 10, 10, 12, 12])]
    for s in subjects:
        rows = [['Admission number', 'Name'] + [f"{w['title']} (/{number(w['max_score']):g})" for w in s['assessments']] + ['Subject %', 'Grade', 'Note']]
        for r in sheet['rows']:
            c = r['cells'][str(s['id'])]
            rows.append([r['admission_number'], r['name']] + [number(c['marks'].get(str(w['id']))) for w in s['assessments']]
                        + [number(c['percent']), c['grade'], c['note'] or None])
        sheets.append((s['name'], rows, [18, 28] + [14] * len(s['assessments']) + [12, 10, 18]))
    labels = sheet['grade_labels']
    analysis = [['Subject', 'Students with marks', 'Mean %', 'Mean grade', 'Highest %', 'Lowest %'] + labels]
    for a in sheet['analysis']:
        analysis.append([a['subject'], a['entries'], number(a['mean']), a['mean_grade'], number(a['highest']), number(a['lowest'])]
                        + [a['grades'].get(label, 0) for label in labels])
    sheets.append(('Subject analysis', analysis, [24, 18, 10, 12, 12, 12] + [6] * len(labels)))
    return workbook_bytes(sheets)
