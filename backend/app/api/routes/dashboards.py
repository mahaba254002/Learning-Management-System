"""Role-specific operational queues; aggregate persisted records, never invented trends."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session
from app.core.deps import AuthContext, get_current_context
from app.db.session import get_db
from app.models.institution import Institution, InstitutionStatus
from app.models.user import User, UserRole, UserStatus
from app.models.academic import AcademicClass, Attendance, Coursework, Enrollment, Score, Student, Subject
from app.models.pilot import AcademicYear
from app.models.learning import Submission
from app.models.audit import AuditEvent
from app.models.subscription import Subscription, SubscriptionPayment
from app.models.curriculum import CourseRegistration
from app.services.subscriptions import kenya_today, subscription_view
from app.services.academic_configuration import academic_configuration
from app.services.learning_settings import learning_settings
from app.api.routes.teaching import scoped, ensure_staff

router = APIRouter(prefix='/api', tags=['Operational dashboards'])


def metric(label, value, detail, href): return dict(label=label, value=value, detail=detail, href=href)


def recent_activity(db, tenant=None):
    q = db.query(AuditEvent, User).outerjoin(User, User.id == AuditEvent.actor_id)
    if tenant: q = q.filter(AuditEvent.institution_id == tenant)
    return [dict(id=row.id, action=row.action.replace('.', ' · ').replace('_', ' '), actor=f'{actor.first_name} {actor.last_name}' if actor else 'Former account', at=row.created_at)
        for row, actor in q.order_by(AuditEvent.created_at.desc(), AuditEvent.id).limit(6).all()]


def platform(db, days):
    institutions = db.query(Institution).filter(Institution.status != InstitutionStatus.ARCHIVED).order_by(Institution.name).all()
    subscriptions = {s.institution_id:s for s in db.query(Subscription).all()}
    admins = {r[0] for r in db.query(User.institution_id).filter(User.role == UserRole.INSTITUTION_ADMIN, User.status == UserStatus.ACTIVE).distinct().all()}
    attention, distribution = [], Counter()
    for row in institutions:
        state = subscription_view(subscriptions.get(row.id)); distribution[state['status']] += 1
        reason = 'Institution suspended' if row.status==InstitutionStatus.SUSPENDED else 'Subscription frozen' if state['frozen'] else 'Payment in grace period' if state['status'] == 'GRACE' else 'Administrator not assigned' if row.id not in admins else 'Academic setup not confirmed' if not row.academic_configuration else None
        if reason:
            attention.append(dict(id=str(row.id), title=row.name, subtitle=f'{row.code} · {row.type.value.replace("_", " ").title()}', status=reason,
                detail=str(state['next_due_date']) if state['next_due_date'] else 'Setup required', href=f'/platform/institutions/{row.id}', urgent=state['frozen'],tone='danger' if state['frozen'] else 'warning' if state['status']=='GRACE' or row.status==InstitutionStatus.SUSPENDED else 'neutral', priority=0 if state['frozen'] else 1 if state['status']=='GRACE' else 2 if row.id not in admins else 3))
    attention.sort(key=lambda r:(r['priority'],r['title']))
    today = kenya_today(); month=today.replace(day=1)
    payment_total = db.query(func.coalesce(func.sum(SubscriptionPayment.amount),0)).filter(SubscriptionPayment.paid_on >= month, SubscriptionPayment.paid_on <= today).scalar()
    months=[]; cursor=month
    for _ in range(6): months.append(cursor); cursor=(cursor-timedelta(days=1)).replace(day=1)
    months.reverse(); totals=defaultdict(Decimal)
    for paid_on, amount in db.query(SubscriptionPayment.paid_on, SubscriptionPayment.amount).filter(SubscriptionPayment.paid_on>=months[0],SubscriptionPayment.paid_on<=today).all(): totals[paid_on.replace(day=1)] += amount
    return dict(title='Platform operations', subtitle='Customer access, recorded payments and service activity.',
        metrics=[metric('Active institutions',sum(r.status==InstitutionStatus.ACTIVE for r in institutions),'Excludes suspended and archived accounts','/platform/institutions'),
            metric('Requires attention',len(attention),'Billing or incomplete customer setup','/platform/institutions'),
            metric('Recorded this month',float(payment_total),'KES · manually verified payment records','/platform/billing'),
            metric('Active accounts',db.query(User).outerjoin(Institution,Institution.id==User.institution_id).filter(User.status==UserStatus.ACTIVE,or_(Institution.status==InstitutionStatus.ACTIVE,User.role==UserRole.PLATFORM_ADMIN)).count(),'Enabled accounts in active institutions','/platform/users')],
        queue_title='Customer attention queue',queue=attention[:12],queue_total=len(attention),
        trend_title='Recorded payments · KES',trend=[dict(label=m.strftime('%b %Y'),value=float(totals[m])) for m in months],
        breakdown=[dict(label=k.replace('_',' ').title(),value=v) for k,v in distribution.items()],
        activity=recent_activity(db),primary=dict(label='Manage institutions',href='/platform/institutions'),
        actions=[dict(title='Billing ledger',detail='Record payments and review due dates',href='/platform/billing'),dict(title='Backup & recovery',detail='Export verified institution or platform archives',href='/platform/backup')])


def staff_dashboard(db, ctx, days, institution, since):
    ensure_staff(db, ctx)
    teacher=ctx.role==UserRole.TEACHER; portal='teacher' if teacher else 'institution'
    labels=learning_settings(institution)
    closed=scoped(db,AcademicYear,ctx).filter_by(status='CLOSED').with_entities(AcademicYear.name)
    classes=scoped(db,AcademicClass,ctx).filter(AcademicClass.academic_year.not_in(closed))
    subjects=scoped(db,Subject,ctx)
    if teacher:
        taught=subjects.filter_by(teacher_id=ctx.user_id).with_entities(Subject.class_id)
        classes=classes.filter((AcademicClass.supervisor_id==ctx.user_id)|(AcademicClass.id.in_(taught)))
        subjects=subjects.filter_by(teacher_id=ctx.user_id)
    groups=classes.order_by(AcademicClass.name).all(); ids=[g.id for g in groups]
    allocations=subjects.filter(Subject.class_id.in_(ids)).all(); subject_ids=[s.id for s in allocations]
    enrollments=scoped(db,Enrollment,ctx).filter(Enrollment.active.is_(True),Enrollment.class_id.in_(ids))
    if teacher:
        entitled=scoped(db,Subject,ctx).filter(Subject.teacher_id==ctx.user_id,Subject.class_id==Enrollment.class_id,
            or_(Subject.registration_mode=='COHORT',scoped(db,CourseRegistration,ctx).filter(CourseRegistration.subject_id==Subject.id,CourseRegistration.student_id==Enrollment.student_id,CourseRegistration.active.is_(True)).exists())).exists()
        enrollments=enrollments.filter(or_(Enrollment.class_id.in_([g.id for g in groups if g.supervisor_id==ctx.user_id]),entitled))
    students=enrollments.all()
    counts=Counter(e.class_id for e in students)
    today=kenya_today()
    rows=scoped(db,Attendance,ctx).join(Enrollment,and_(Enrollment.institution_id==Attendance.institution_id,Enrollment.class_id==Attendance.class_id,Enrollment.student_id==Attendance.student_id,Enrollment.active.is_(True))).filter(Attendance.class_id.in_(ids),Attendance.day==today,Attendance.scope_key=='class').all()
    covered=Counter(r.class_id for r in rows)
    queue=[]
    for group in groups:
        if counts[group.id] and (not teacher or group.supervisor_id==ctx.user_id):
            queue.append(dict(id=str(group.id),title=group.name,subtitle=group.academic_year,status='Complete' if covered[group.id]>=counts[group.id] else 'Register incomplete',
                detail=f'{covered[group.id]} / {counts[group.id]} recorded today',href=f'/{portal}/attendance?register=class:{group.id}',urgent=covered[group.id]<counts[group.id]))
    # Subject lecturers receive actionable course registers too, not another teacher's class register.
    if teacher:
        from app.api.routes.teaching import subject_students
        for subject in allocations:
            total=subject_students(db,subject,ctx).count()
            marked=subject_students(db,subject,ctx).join(Attendance,and_(Attendance.institution_id==Student.institution_id,Attendance.student_id==Student.id,Attendance.class_id==subject.class_id,Attendance.subject_id==subject.id,Attendance.day==today)).count()
            if total: queue.append(dict(id=str(subject.id),title=subject.name,subtitle=next(g.name for g in groups if g.id==subject.class_id),status='Complete' if marked>=total else 'Register incomplete',detail=f'{marked} / {total} subject attendance',href=f'/{portal}/attendance?register=subject:{subject.id}',urgent=marked<total))
    queue.sort(key=lambda r:(not r['urgent'],r['title']))
    work_query=scoped(db,Coursework,ctx).filter(Coursework.subject_id.in_(subject_ids))
    work_ids=work_query.with_entities(Coursework.id)
    # Aggregate on the database rather than downloading every mark and answer.
    unmarked=scoped(db,Submission,ctx).join(Coursework,Coursework.id==Submission.coursework_id).join(Subject,Subject.id==Coursework.subject_id).join(Enrollment,and_(Enrollment.institution_id==Submission.institution_id,Enrollment.class_id==Subject.class_id,Enrollment.student_id==Submission.student_id,Enrollment.active.is_(True))).outerjoin(Score,and_(Score.institution_id==Submission.institution_id,
        Score.coursework_id==Submission.coursework_id,Score.student_id==Submission.student_id)).filter(
        Submission.coursework_id.in_(work_ids),Submission.status=='SUBMITTED',Score.id.is_(None),or_(Subject.registration_mode=='COHORT',scoped(db,CourseRegistration,ctx).filter(CourseRegistration.subject_id==Subject.id,CourseRegistration.student_id==Submission.student_id,CourseRegistration.active.is_(True)).exists()))
    marking=dict(unmarked.with_entities(Submission.coursework_id,func.count(Submission.id)).group_by(Submission.coursework_id).all())
    review_works=work_query.filter(Coursework.id.in_(marking)).order_by(Coursework.due_at,Coursework.created_at).limit(8).all()
    actions=[dict(title=f'{w.title} · {marking[w.id]} to review',detail='Final submissions without a recorded outcome',href=f'/{portal}/scores?subject={w.subject_id}&assessment={w.id}') for w in review_works]
    if not teacher:
        missing=sum(g.supervisor_id is None for g in groups)
        if missing: actions.insert(0,dict(title=f'{missing} groups need a supervisor',detail='Complete teaching responsibility assignments',href='/institution/classes'))
        if not scoped(db,AcademicYear,ctx).filter_by(status='ACTIVE').first(): actions.insert(0,dict(title='No active academic year',detail='Review calendar dates and activate the current year',href='/institution/academic-years'))
        if not institution.academic_configuration: actions.insert(0,dict(title='Academic policy needs confirmation',detail='Ask platform admin to confirm your institution setup',href='/institution/settings'))
    released=work_query.filter(Coursework.published.is_(True),Coursework.grades_released.is_(True)).count()
    attendance=scoped(db,Attendance,ctx).filter(Attendance.class_id.in_(ids),Attendance.scope_key=='class',Attendance.day>=since,Attendance.day<=today)
    if teacher:
        supervised=[g.id for g in groups if g.supervisor_id==ctx.user_id]
        attendance=attendance.filter(Attendance.class_id.in_(supervised))
    trends=defaultdict(lambda:Counter())
    for day,status,count in attendance.with_entities(Attendance.day,Attendance.status,func.count(Attendance.id)).group_by(Attendance.day,Attendance.status).all():trends[day][status]+=count
    series=[]
    for offset in range(days):
        day=since+timedelta(days=offset); count=trends[day]; denominator=count['PRESENT']+count['LATE']+count['ABSENT']
        series.append(dict(label=day.isoformat(),value=round((count['PRESENT']+count['LATE'])/denominator*100,1) if denominator else None))
    return dict(title='Teaching workspace' if teacher else institution.name,subtitle='Your registers, learner work and teaching responsibilities.' if teacher else 'Academic operations and institution readiness.',
        metrics=[metric('Teaching groups' if teacher else f'{labels["class_label"]}{"es" if labels["class_label"].endswith("s") else "s"}',len(groups),'Open academic years',f'/{portal}/classes'),
            metric('Learners enrolled',len({e.student_id for e in students}),'Distinct learners in your visible groups',f'/{portal}/classes'),
            metric('Awaiting marking',sum(marking.values()),'Final submissions without a recorded outcome',f'/{portal}/scores'),
            metric('Results released',released,'Published assessments visible to learners',f'/{portal}/scores')],
        queue_title='Today’s attendance registers',queue=queue[:12],queue_total=len(queue),actions=actions[:8],
        trend_title='Daily class attendance · % present or late',trend=series,breakdown=[],
        activity=[] if teacher else recent_activity(db,ctx.institution_id),primary=dict(label='Open teaching groups',href=f'/{portal}/classes'))


def student_dashboard(db,ctx,days,institution,since):
    from app.api.routes.learning import assignments, own_student, student_subjects
    student=own_student(db,ctx); subjects=student_subjects(db,student,ctx).all()
    works=assignments(None,db,ctx)
    pending=[w for w in works if not w['academic_year_closed'] and w['kind']!='EXAM' and not w['submission_locked'] and (not w['submission'] or w['submission']['status']!='SUBMITTED')]
    pending.sort(key=lambda w:w['due_at'] or datetime.max.replace(tzinfo=timezone.utc))
    today=kenya_today(); queue=[]
    for w in pending[:8]:
        overdue=bool(w['due_at'] and w['due_at']<datetime.now(timezone.utc))
        queue.append(dict(id=str(w['id']),title=w['title'],subtitle=w['subject_name'],status='Overdue' if overdue else 'Draft saved' if w['submission'] else 'To do',
            detail=w['due_at'].isoformat() if w['due_at'] else 'No deadline',href=f'/student/assignments/{w["id"]}',urgent=overdue))
    attendance=scoped(db,Attendance,ctx).filter(Attendance.student_id==student.id,Attendance.scope_key=='class',Attendance.day>=since,Attendance.day<=today).all()
    statuses=Counter(r.status for r in attendance); denominator=statuses['PRESENT']+statuses['LATE']+statuses['ABSENT']
    rate=round((statuses['PRESENT']+statuses['LATE'])/denominator*100,1) if denominator else None
    trends=defaultdict(Counter)
    for row in attendance:trends[row.day][row.status]+=1
    series=[]
    for offset in range(days):
        day=since+timedelta(days=offset); d=trends[day]; total=d['PRESENT']+d['LATE']+d['ABSENT']
        series.append(dict(label=day.isoformat(),value=round((d['PRESENT']+d['LATE'])/total*100,1) if total else None))
    feedback=[dict(title=w['title'],detail=w['competency_label'] or f'{w["score"]} / {w["max_score"]}',href=f'/student/assignments/{w["id"]}') for w in works if w['graded']][:6]
    return dict(title='My learning',subtitle='Your next tasks, attendance and released feedback.',
        metrics=[metric('Learning offerings',len(subjects),'Registered subjects, courses or learning areas','/student/subjects'),metric('Tasks to complete',len(pending),'Open assignments not yet submitted','/student/assignments'),
            metric('Attendance',f'{rate}%' if rate is not None else '—',f'{denominator} marked sessions · excused excluded','/student/attendance'),metric('Released outcomes',sum(w['graded'] for w in works),'Marks and competency feedback you can view','/student/grades')],
        queue_title='Your next assignments',queue=queue,queue_total=len(pending),actions=feedback,trend_title='My daily attendance · %',trend=series,
        breakdown=[dict(label=k.title(),value=v) for k,v in statuses.items()],activity=[],primary=dict(label='Open assignments',href='/student/assignments'))


@router.get('/dashboard')
def dashboard(days:int=Query(30,ge=7,le=90),db:Session=Depends(get_db),ctx:AuthContext=Depends(get_current_context)):
    today=kenya_today(); since=today-timedelta(days=days-1)
    if ctx.role==UserRole.PLATFORM_ADMIN: result=platform(db,days); institution=None
    else:
        institution=db.get(Institution,ctx.institution_id)
        result=student_dashboard(db,ctx,days,institution,since) if ctx.role==UserRole.STUDENT else staff_dashboard(db,ctx,days,institution,since)
    return dict(**result,role=ctx.role,generated_at=datetime.now(timezone.utc),since=since,today=today,days=days,
        configuration=academic_configuration(institution) if institution else None,labels=learning_settings(institution) if institution else None,
        institution=dict(name=institution.name,code=institution.code,type=institution.type) if institution else None)
