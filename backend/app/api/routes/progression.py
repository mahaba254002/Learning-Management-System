import uuid
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import AuthContext,require_platform_admin
from app.db.session import get_db
from app.api.routes.teaching import admin,scoped,commit
from app.models.academic import AcademicClass,Enrollment,Student,Subject
from app.models.curriculum import CatalogueUnit
from app.models.institution import Institution,InstitutionStatus
from app.models.pilot import AcademicYear
from app.models.progression import Prerequisite,ProgressionDecision
from app.schemas.academic import Input
from app.services import progression as service
from app.services.audit_service import record_audit

router=APIRouter(prefix='/api',tags=['Progression and prerequisites'])


class Requirement(Input):
    required_id:uuid.UUID
    minimum_percentage:float|None=Field(default=None,ge=0,le=100,multiple_of=0.0001,allow_inf_nan=False)


class Requirements(Input):
    requirements:list[Requirement]=Field(max_length=20)
    expected_updated_at:str=Field(max_length=60)


@router.get('/platform/institutions/{institution_id}/prerequisites')
def prerequisites(institution_id:uuid.UUID,db:Session=Depends(get_db),ctx:AuthContext=Depends(require_platform_admin)):
    institution=db.get(Institution,institution_id)
    if not institution:raise HTTPException(404,'Institution not found')
    return dict(updated_at=institution.updated_at,courses=[dict(id=c.id,code=c.code,name=c.name) for c in db.query(CatalogueUnit).filter_by(institution_id=institution_id).order_by(CatalogueUnit.code)],
        links=[dict(course_id=r.course_id,required_id=r.required_id,minimum_percentage=r.minimum_percentage) for r in db.query(Prerequisite).filter_by(institution_id=institution_id)])


@router.put('/platform/institutions/{institution_id}/prerequisites/{course_id}')
def set_prerequisites(institution_id:uuid.UUID,course_id:uuid.UUID,body:Requirements,db:Session=Depends(get_db),ctx:AuthContext=Depends(require_platform_admin)):
    institution=db.query(Institution).filter_by(id=institution_id).with_for_update().first()
    if not institution:raise HTTPException(404,'Institution not found')
    if institution.status==InstitutionStatus.ARCHIVED:raise HTTPException(409,'Archived institution cannot be changed')
    from datetime import datetime, timezone
    def utc(value):
        value = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    try: fresh = utc(institution.updated_at) == utc(body.expected_updated_at)
    except ValueError: fresh = False
    if not fresh: raise HTTPException(409, 'Configuration changed. Refresh prerequisites.')
    owned={c.id for c in db.query(CatalogueUnit).filter_by(institution_id=institution_id)}
    selected=[r.required_id for r in body.requirements]
    if course_id not in owned or not set(selected).issubset(owned):raise HTTPException(404,'Catalogue course not found')
    if len(set(selected))!=len(selected) or course_id in selected:raise HTTPException(422,'Use distinct prerequisites; a course cannot require itself')
    graph={}
    for r in db.query(Prerequisite).filter_by(institution_id=institution_id):graph.setdefault(r.course_id,[]).append(r.required_id)
    graph[course_id]=selected
    # Adding course -> required creates a cycle only if required can reach course.
    pending=list(selected);visited=set()
    while pending:
        node=pending.pop()
        if node==course_id:raise HTTPException(422,'Prerequisites would form a cycle')
        if node not in visited:
            visited.add(node);pending.extend(graph.get(node,[]))
    db.query(Prerequisite).filter_by(institution_id=institution_id,course_id=course_id).delete()
    for r in body.requirements:db.add(Prerequisite(institution_id=institution_id,course_id=course_id,required_id=r.required_id,minimum_percentage=str(r.minimum_percentage) if r.minimum_percentage is not None else None))
    from datetime import datetime,timezone
    institution.updated_at=datetime.now(timezone.utc)
    record_audit(db,ctx,'prerequisites.updated',course_id,institution_id)
    commit(db);return dict(saved=True)


class DecisionInput(Input):
    student_id:uuid.UUID
    source_class_id:uuid.UUID
    target_class_id:uuid.UUID|None=None
    decision:Literal['ADVANCE','REPEAT','COMPLETE']='ADVANCE'
    expected_digest:str|None=Field(default=None,max_length=64)
    override_reason:str=Field(default='',max_length=1000)


def evaluate(db,ctx,body):
    source=scoped(db,AcademicClass,ctx).filter_by(id=body.source_class_id).first()
    target=scoped(db,AcademicClass,ctx).filter_by(id=body.target_class_id).first() if body.target_class_id else None
    student=scoped(db,Student,ctx).filter_by(id=body.student_id).first()
    if not source or not student or body.target_class_id and not target:raise HTTPException(404,'Progression record not found')
    if body.decision=='COMPLETE' and target:raise HTTPException(422,'Completion must not have a destination group')
    if scoped(db,ProgressionDecision,ctx).filter_by(source_class_id=source.id,student_id=student.id).first():raise HTTPException(409,'A decision already exists for this source enrollment')
    return service.evaluate(db,ctx.institution_id,student.id,source,target,body.decision)


@router.post('/institution/progression/preview')
def preview(body:DecisionInput,db:Session=Depends(get_db),ctx:AuthContext=Depends(admin)):
    return evaluate(db,ctx,body)


@router.post('/institution/progression/approve',status_code=201)
def approve(body:DecisionInput,db:Session=Depends(get_db),ctx:AuthContext=Depends(admin)):
    db.query(Institution).filter_by(id=ctx.institution_id).with_for_update().one()
    scoped(db,AcademicYear,ctx).order_by(AcademicYear.start_date).with_for_update().all()
    scoped(db,AcademicClass,ctx).filter(AcademicClass.id.in_([body.source_class_id,body.target_class_id])).order_by(AcademicClass.id).with_for_update().all()
    data=evaluate(db,ctx,body)
    if data['digest']!=body.expected_digest:raise HTTPException(409,'Eligibility changed. Preview again.')
    if data['structural']:raise HTTPException(409,'Resolve structural issues: '+'; '.join(data['structural']))
    if data['blockers'] and (not data['policy']['allow_override'] or len(body.override_reason.strip())<10):raise HTTPException(409,'Resolve eligibility requirements or provide a permitted override reason of at least ten characters.')
    if body.target_class_id:
        row=scoped(db,Enrollment,ctx).filter_by(class_id=body.target_class_id,student_id=body.student_id).first()
        if row and row.active:raise HTTPException(409,'Learner is already enrolled in this destination')
        if row:row.active=True
        else:db.add(Enrollment(institution_id=ctx.institution_id,class_id=body.target_class_id,student_id=body.student_id))
    row=ProgressionDecision(institution_id=ctx.institution_id,source_class_id=body.source_class_id,target_class_id=body.target_class_id,student_id=body.student_id,decision=body.decision,snapshot={**data,'override_reason':body.override_reason.strip()})
    db.add(row);db.flush();record_audit(db,ctx,'student.progression_approved',row.id,ctx.institution_id,body.decision);commit(db)
    return dict(id=row.id,message='Decision saved. Historical enrollment and academic records were retained.')


@router.get('/institution/progression/history')
def history(db:Session=Depends(get_db),ctx:AuthContext=Depends(admin)):
    return [decision_view(db,r) for r in scoped(db,ProgressionDecision,ctx).order_by(ProgressionDecision.created_at.desc()).limit(50)]


def decision_view(db, row, student_view=False):
    from app.models.user import User
    learner=db.get(Student,row.student_id);user=db.get(User,learner.user_id)
    source=db.get(AcademicClass,row.source_class_id)
    target=db.get(AcademicClass,row.target_class_id) if row.target_class_id else None
    data=dict(id=row.id,learner=f'{user.first_name} {user.last_name}',admission_number=learner.admission_number,
        source=f'{source.name} · {source.academic_year}',destination=f'{target.name} · {target.academic_year}' if target else 'Programme / level completed',
        decision=row.decision,created_at=row.created_at,metrics=row.snapshot['metrics'])
    if not student_view:data['snapshot']=row.snapshot
    return data


from app.core.deps import require_tenant_user
from app.models.user import UserRole
@router.get('/student/progression')
def student_history(db:Session=Depends(get_db),ctx:AuthContext=Depends(require_tenant_user)):
    from app.api.routes.learning import own_student
    if ctx.role!=UserRole.STUDENT:raise HTTPException(403,'Student access required')
    student=own_student(db,ctx)
    return [decision_view(db,r,True) for r in scoped(db,ProgressionDecision,ctx).filter_by(student_id=student.id).order_by(ProgressionDecision.created_at.desc())]
