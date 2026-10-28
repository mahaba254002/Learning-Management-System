import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import AuthContext
from app.db.session import get_db
from app.api.routes.teaching import staff,admin,scoped,get_subject,get_class,subject_students,commit
from app.models.academic import Subject,Student
from app.models.curriculum import CourseCompletion,CatalogueUnit
from app.models.final_grade import FinalGrade
from app.schemas.academic import Input
from app.services import final_grades as grades
from app.services.audit_service import record_audit

router=APIRouter(prefix='/api',tags=['Final grades'])


class Approval(Input):
    student_id:uuid.UUID
    period_id:uuid.UUID|None=None
    expected_digest:str=Field(pattern=r'^[a-f0-9]{64}$')
    expected_updated_at:str|None=Field(default=None,max_length=60)
    released:bool=True


@router.get('/teaching/subjects/{subject_id}/final-grades')
def preview(subject_id:uuid.UUID,period_id:uuid.UUID|None=None,db:Session=Depends(get_db),ctx:AuthContext=Depends(staff)):
    subject=get_subject(db,subject_id,ctx);scope=grades.scope_period(db,subject,period_id)
    existing={r.student_id:r for r in scoped(db,FinalGrade,ctx).filter_by(subject_id=subject.id,scope=scope).all()}
    students=[]
    people=subject_students(db,subject,ctx).all()
    prepared=grades.prepare(db,subject,[s.id for s,_ in people])
    for student,user in people:
        saved=existing.get(student.id);data=grades.compute(db,subject,student.id,scope,prepared)
        students.append(dict(id=student.id,name=f'{user.first_name} {user.last_name}',admission_number=student.admission_number,**data,
            approved=bool(saved),released=saved.released if saved else False,stale=bool(saved and saved.source_digest!=data['source_digest']),
            updated_at=saved.updated_at if saved else None))
    return dict(policy=grades.policy_for(db,subject),pinned=subject.grading_policy is not None,scope=scope,students=students)


@router.put('/institution/subjects/{subject_id}/final-grades')
def approve(subject_id:uuid.UUID,body:Approval,db:Session=Depends(get_db),ctx:AuthContext=Depends(admin)):
    subject=get_subject(db,subject_id,ctx);get_class(db,subject.class_id,ctx,lock=True)
    subject=scoped(db,Subject,ctx).filter_by(id=subject_id).with_for_update().populate_existing().one()
    if not subject_students(db,subject,ctx).filter(Student.id==body.student_id).first():raise HTTPException(404,'Learner not registered for this offering')
    scope=grades.scope_period(db,subject,body.period_id)
    row=scoped(db,FinalGrade,ctx).filter_by(subject_id=subject.id,student_id=body.student_id,scope=scope).first()
    if (row.updated_at.isoformat() if row else None)!=body.expected_updated_at:raise HTTPException(409,'Final grade changed. Reload before approval.')
    data=grades.compute(db,subject,body.student_id,scope)
    if data['source_digest']!=body.expected_digest:raise HTTPException(409,'Marks or grading rules changed. Review the new calculation.')
    if body.released:
        if not data['ready']:raise HTTPException(409,'Resolve incomplete grading requirements before approval.')
        if subject.grading_policy is None:subject.grading_policy=data['result']['policy']
        if not row:
            row=FinalGrade(institution_id=ctx.institution_id,subject_id=subject.id,student_id=body.student_id,scope=scope)
            db.add(row)
        row.source_digest=data['source_digest'];row.result=data['result'];row.released=True
        if scope=='ALL' and subject.catalogue_id:
            completion=scoped(db,CourseCompletion,ctx).filter_by(subject_id=subject.id,student_id=body.student_id).first()
            if completion and completion.outcome=='EXEMPT':raise HTTPException(409,'This offering is exempt. Resolve exemption before approving a numeric final grade.')
            unit=db.get(CatalogueUnit,subject.catalogue_id)
            if not completion:
                completion=CourseCompletion(institution_id=ctx.institution_id,subject_id=subject.id,student_id=body.student_id);db.add(completion)
            completion.outcome='PASSED' if row.result['passed'] else 'FAILED';completion.released=True;completion.credits=unit.credits or 0
    else:
        if not row:raise HTTPException(404,'No final grade to withhold')
        row.released=False
        if scope=='ALL':
            completion=scoped(db,CourseCompletion,ctx).filter_by(subject_id=subject.id,student_id=body.student_id).first()
            if completion and completion.outcome!='EXEMPT':completion.released=False
    record_audit(db,ctx,'final_grade.released' if body.released else 'final_grade.withheld',subject.id,ctx.institution_id,scope)
    commit(db)
    return dict(released=row.released,result=row.result,updated_at=row.updated_at)
