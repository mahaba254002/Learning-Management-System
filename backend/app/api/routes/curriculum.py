import uuid
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import AuthContext, require_platform_admin, require_tenant_user
from app.db.session import get_db
from app.models.institution import Institution, InstitutionType, InstitutionStatus
from app.models.curriculum import Department, Programme, StudyLevel, CatalogueUnit, CourseRegistration, CourseCompletion
from app.models.academic import AcademicClass, Coursework, Enrollment, Student, Subject
from app.models.user import User
from app.schemas.academic import Input
from app.services.academic_configuration import AcademicConfiguration, academic_configuration, template
from app.services.learning_settings import LearningSettings, learning_settings
from app.services.audit_service import record_audit
from app.api.routes.teaching import admin, staff, scoped, get_subject, get_class, enrolled_students, commit

router = APIRouter(prefix='/api', tags=['Academic structure'])


class ConfigurationInput(Input):
    configuration: AcademicConfiguration
    labels: LearningSettings
    expected_updated_at: str = Field(max_length=60)


@router.get('/platform/academic-templates')
def templates(ctx: AuthContext = Depends(require_platform_admin)):
    return [dict(type=kind.value, configuration=template(kind), labels=learning_settings(Institution(type=kind, learning_settings={}))) for kind in InstitutionType]


@router.get('/platform/institutions/{institution_id}/academic-configuration')
def platform_configuration(institution_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    row = db.get(Institution, institution_id)
    if not row: raise HTTPException(404, 'Institution not found')
    return dict(configuration=academic_configuration(row), labels=learning_settings(row), updated_at=row.updated_at, managed=bool(row.academic_configuration))


@router.put('/platform/institutions/{institution_id}/academic-configuration')
def configure(institution_id: uuid.UUID, body: ConfigurationInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    row = db.query(Institution).filter_by(id=institution_id).with_for_update().first()
    if not row: raise HTTPException(404, 'Institution not found')
    if row.status == InstitutionStatus.ARCHIVED: raise HTTPException(409, 'Archived institutions cannot be configured')
    if row.updated_at.isoformat() != body.expected_updated_at: raise HTTPException(409, 'Institution changed. Reload configuration before saving.')
    if body.configuration.structure == 'GROUPED' and db.query(Programme.id).filter_by(institution_id=row.id).first():
        raise HTTPException(409, 'Programmes already exist. Keep programme structure enabled.')
    if not body.configuration.credits_enabled and db.query(CatalogueUnit.id).filter(CatalogueUnit.institution_id == row.id, CatalogueUnit.credits > 0).first():
        raise HTTPException(409, 'Credit-bearing courses exist. Credits cannot be disabled.')
    if body.configuration.assessment_policy != 'MIXED':
        incompatible = 'NUMERIC' if body.configuration.assessment_policy == 'COMPETENCY' else 'COMPETENCY'
        if db.query(Coursework.id).filter_by(institution_id=row.id, assessment_mode=incompatible).first():
            raise HTTPException(409, 'Existing assessments require mixed assessment policy. Their history cannot be reinterpreted.')
    row.academic_configuration = body.configuration.model_dump()
    row.learning_settings = body.labels.model_dump()
    record_audit(db, ctx, 'institution.academic_configuration_updated', row.id, row.id)
    commit(db)
    return platform_configuration(row.id, db, ctx)


@router.get('/institution/academic-configuration')
def configuration(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    row = db.get(Institution, ctx.institution_id)
    return dict(**academic_configuration(row), labels=learning_settings(row), managed=bool(row.academic_configuration))


class StructureInput(Input):
    code: str = Field(min_length=1, max_length=30, pattern=r'^[A-Za-z0-9._/-]+$')
    name: str = Field(min_length=1, max_length=100)
    department_id: uuid.UUID | None = None
    programme_id: uuid.UUID | None = None
    level_id: uuid.UUID | None = None
    award: str | None = Field(default=None, max_length=100)
    position: int = Field(default=1, ge=1, le=100)
    credits: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=6, decimal_places=2)
    expected_updated_at: str | None = Field(default=None, max_length=60)


MODELS = dict(departments=Department, programmes=Programme, levels=StudyLevel, catalogue=CatalogueUnit)


def owned(db, model, identity, tenant):
    if identity is None: return None
    row = db.query(model).filter_by(id=identity, institution_id=tenant).first()
    if not row: raise HTTPException(404, 'Academic structure record not found')
    return row


def validate_links(db, tenant, programme_id=None, level_id=None):
    programme = owned(db, Programme, programme_id, tenant)
    level = owned(db, StudyLevel, level_id, tenant)
    if level and level.programme_id != programme_id: raise HTTPException(422, 'Study level must belong to the selected programme or school structure')
    return programme, level


@router.get('/institution/academic-structure')
def structure(db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    return {kind: [dict((column.name, getattr(row, column.name)) for column in model.__table__.columns if column.name not in {'created_at', 'institution_id'})
                   for row in scoped(db, model, ctx).order_by(model.code).all()] for kind, model in MODELS.items()}


@router.post('/institution/academic-structure/{kind}', status_code=201)
def create_structure(kind: Literal['departments', 'programmes', 'levels', 'catalogue'], body: StructureInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    config = academic_configuration(db.get(Institution, ctx.institution_id))
    model = MODELS[kind]
    if kind in {'departments', 'programmes'} and config['structure'] != 'PROGRAMME': raise HTTPException(409, 'Platform admin must enable programme structure first')
    if body.programme_id and config['structure'] != 'PROGRAMME': raise HTTPException(409, 'Programme structure is not enabled')
    owned(db, Department, body.department_id, ctx.institution_id)
    validate_links(db, ctx.institution_id, body.programme_id, body.level_id)
    if body.credits is not None and not config['credits_enabled']: raise HTTPException(409, 'Platform admin must enable course credits first')
    keys = {'departments': ['code', 'name'], 'programmes': ['code', 'name', 'department_id', 'award'], 'levels': ['code', 'name', 'programme_id', 'position'], 'catalogue': ['code', 'name', 'programme_id', 'level_id', 'credits']}[kind]
    row = model(id=uuid.uuid4(), institution_id=ctx.institution_id, **{key: getattr(body, key) for key in keys})
    row.code = row.code.upper()
    db.add(row); record_audit(db, ctx, f'academic_structure.{kind}_created', row.id, ctx.institution_id)
    commit(db)
    return dict(id=row.id)


@router.put('/institution/academic-structure/{kind}/{record_id}')
def edit_structure(kind: Literal['departments', 'programmes', 'levels', 'catalogue'], record_id: uuid.UUID, body: StructureInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    model=MODELS[kind]
    row=scoped(db,model,ctx).filter_by(id=record_id).with_for_update().first()
    if not row: raise HTTPException(404, 'Academic record not found')
    if body.expected_updated_at != row.updated_at.isoformat(): raise HTTPException(409,'This academic record changed. Reload before editing.')
    owned(db,Department,body.department_id,ctx.institution_id)
    validate_links(db,ctx.institution_id,body.programme_id,body.level_id)
    if kind=='levels' and row.programme_id!=body.programme_id:
        if scoped(db,AcademicClass,ctx).filter_by(level_id=row.id).first() or scoped(db,CatalogueUnit,ctx).filter_by(level_id=row.id).first(): raise HTTPException(409,'This level is in use; its programme cannot be reassigned.')
    if kind=='catalogue':
        if (row.programme_id,row.level_id,row.credits)!=(body.programme_id,body.level_id,body.credits) and scoped(db,Subject,ctx).filter_by(catalogue_id=row.id).first():
            raise HTTPException(409,'This catalogue course has teaching offerings. Create a new catalogue entry to change its programme, level or credits.')
        if body.credits is not None and not academic_configuration(db.get(Institution,ctx.institution_id))['credits_enabled']: raise HTTPException(409,'Course credits are not enabled')
    keys={'departments':['code','name'],'programmes':['code','name','department_id','award'],'levels':['code','name','programme_id','position'],'catalogue':['code','name','programme_id','level_id','credits']}[kind]
    for key in keys:setattr(row,key,getattr(body,key))
    row.code=row.code.upper()
    record_audit(db,ctx,f'academic_structure.{kind}_updated',row.id,ctx.institution_id)
    commit(db)
    return dict(id=row.id)


@router.get('/teaching/subjects/{subject_id}/students')
def subject_roster(subject_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    from app.api.routes.teaching import subject_students, student_view
    subject = get_subject(db, subject_id, ctx)
    return [student_view(s, u) for s, u in subject_students(db, subject, ctx).order_by(User.first_name, User.last_name).all()]


@router.get('/institution/subjects/{subject_id}/registrations')
def registrations(subject_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    from app.api.routes.teaching import student_view
    from app.services.progression import course_check
    subject = get_subject(db, subject_id, ctx)
    registered = {r.student_id for r in scoped(db, CourseRegistration, ctx).filter_by(subject_id=subject.id, active=True).all()}
    completed = {r.student_id: r for r in scoped(db, CourseCompletion, ctx).filter_by(subject_id=subject.id).all()}
    return dict(mode=subject.registration_mode, students=[dict(**student_view(s, u), registered=subject.registration_mode == 'COHORT' or s.id in registered)
        | dict(entry_issues=course_check(db,ctx.institution_id,s.id,subject) if s.id not in registered else [], completion=completed[s.id].outcome if s.id in completed else None, completion_updated_at=completed[s.id].updated_at if s.id in completed else None)
        for s, u in enrolled_students(db, subject.class_id, ctx).all()])


class RegistrationInput(Input):
    student_id: uuid.UUID
    active: bool


@router.put('/institution/subjects/{subject_id}/registrations')
def register(subject_id: uuid.UUID, body: RegistrationInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    from app.services.progression import lock_entry
    lock_entry(db, ctx.institution_id)
    subject = get_subject(db, subject_id, ctx)
    get_class(db, subject.class_id, ctx, lock=True)
    if subject.registration_mode != 'INDIVIDUAL': raise HTTPException(409, 'This offering uses whole-cohort enrollment')
    if not enrolled_students(db, subject.class_id, ctx).filter(Student.id == body.student_id).first(): raise HTTPException(404, 'Student is not enrolled in this cohort')
    row = scoped(db, CourseRegistration, ctx).filter_by(subject_id=subject.id, student_id=body.student_id).first()
    from app.services.progression import assert_course
    if body.active and (not row or not row.active): assert_course(db, ctx.institution_id, body.student_id, subject)
    if row: row.active = body.active
    else: db.add(CourseRegistration(institution_id=ctx.institution_id, subject_id=subject.id, student_id=body.student_id, active=body.active))
    record_audit(db, ctx, 'course.registration_changed', subject.id, ctx.institution_id, f'{body.student_id}: {body.active}')
    commit(db)
    return dict(active=body.active)


class CompletionInput(Input):
    student_id: uuid.UUID
    outcome: Literal['PASSED', 'FAILED', 'EXEMPT']
    released: bool = False
    expected_updated_at: str | None = Field(default=None, max_length=60)


@router.put('/institution/subjects/{subject_id}/completion')
def complete(subject_id: uuid.UUID, body: CompletionInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    from app.api.routes.teaching import subject_students
    subject = get_subject(db, subject_id, ctx)
    get_class(db, subject.class_id, ctx, lock=True)
    if not subject_students(db, subject, ctx).filter(Student.id == body.student_id).first(): raise HTTPException(404, 'Student is not registered for this offering')
    unit = owned(db, CatalogueUnit, subject.catalogue_id, ctx.institution_id)
    if not unit: raise HTTPException(409, 'Link an offering to the catalogue before approving completion')
    from app.models.final_grade import FinalGrade
    if scoped(db, FinalGrade, ctx).filter_by(subject_id=subject.id,student_id=body.student_id,scope='ALL',released=True).first():
        raise HTTPException(409, 'Withhold the approved final grade before manually changing course completion')
    row = scoped(db, CourseCompletion, ctx).filter_by(subject_id=subject.id, student_id=body.student_id).first()
    if row and body.expected_updated_at != row.updated_at.isoformat(): raise HTTPException(409, 'Course outcome changed. Reload before approving another change.')
    if not row:
        row = CourseCompletion(institution_id=ctx.institution_id, subject_id=subject.id, student_id=body.student_id)
        db.add(row)
    row.outcome, row.released = body.outcome, body.released
    row.credits = unit.credits or 0
    record_audit(db, ctx, 'course.completion_approved', subject.id, ctx.institution_id, f'{body.student_id}: {body.outcome}; released={body.released}')
    commit(db)
    return dict(outcome=row.outcome, credits=row.credits, released=row.released)


@router.get('/student/academic-record')
def academic_record(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    from app.models.user import UserRole
    from app.api.routes.learning import own_student
    if ctx.role != UserRole.STUDENT: raise HTTPException(403, 'Student access required')
    student = own_student(db, ctx)
    rows = scoped(db, CourseCompletion, ctx).join(Subject, Subject.id == CourseCompletion.subject_id).join(AcademicClass, AcademicClass.id == Subject.class_id).filter(
        CourseCompletion.student_id == student.id, CourseCompletion.released.is_(True)).with_entities(CourseCompletion, Subject, AcademicClass).all()
    earned = {}
    for result, subject, _ in rows:
        if result.outcome in {'PASSED', 'EXEMPT'}:
            key = subject.catalogue_id or subject.id
            earned[key] = max(earned.get(key, Decimal('0')), result.credits)
    from app.services.final_grades import academic_results, current
    from app.models.final_grade import FinalGrade
    # A changed/withheld assessment cannot leave stale derived credits visible.
    approved={r.subject_id:r for r in scoped(db,FinalGrade,ctx).filter_by(student_id=student.id,scope='ALL').all()}
    rows=[(r,s,c) for r,s,c in rows if r.outcome=='EXEMPT' or s.id not in approved or current(db,approved[s.id],s)]
    earned={}
    for r,s,_ in rows:
        if r.outcome in {'PASSED','EXEMPT'}: earned[s.catalogue_id or s.id]=max(earned.get(s.catalogue_id or s.id,Decimal('0')),r.credits)
    return dict(**academic_results(db,ctx.institution_id,student.id),earned_credits=sum(earned.values(), Decimal('0')),
        courses=[dict(id=r.id, course=s.name, academic_year=c.academic_year, outcome=r.outcome, credits=r.credits) for r, s, c in rows])
