"""Explicit platform-authorized recalculation; issued documents remain immutable."""
import uuid
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import Field
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.deps import AuthContext,require_platform_admin
from app.db.session import get_db
from app.models.academic import Subject,AcademicClass
from app.models.curriculum import CourseCompletion
from app.models.final_grade import FinalGrade
from app.models.institution import Institution,InstitutionStatus
from app.schemas.academic import Input
from app.services.academic_calendar import writable_year
from app.services.academic_configuration import academic_configuration
from app.services.audit_service import record_audit
from app.api.routes.teaching import commit

router=APIRouter(prefix='/api/platform/institutions',tags=['Platform grading policies'])


class ApplyPolicy(Input):
    expected_subject_updated_at:str=Field(max_length=60)
    expected_institution_updated_at:str=Field(max_length=60)
    confirmation:str=Field(min_length=1,max_length=120)


@router.get('/{institution_id}/grading-offerings')
def offerings(institution_id:uuid.UUID,search:str=Query('',max_length=100),db:Session=Depends(get_db),ctx:AuthContext=Depends(require_platform_admin)):
    institution=db.get(Institution,institution_id)
    if not institution:raise HTTPException(404,'Institution not found')
    rows=db.query(Subject,AcademicClass).join(AcademicClass,AcademicClass.id==Subject.class_id).filter(Subject.institution_id==institution_id)
    if search:rows=rows.filter(or_(Subject.name.ilike('%'+search+'%'),AcademicClass.name.ilike('%'+search+'%')))
    return dict(institution_updated_at=institution.updated_at,items=[dict(id=s.id,name=s.name,group=c.name,year=c.academic_year,
        updated_at=s.updated_at,policy_name=s.grading_policy['name'] if s.grading_policy else 'Not yet pinned') for s,c in rows.order_by(Subject.name,Subject.id).limit(100).all()])


@router.put('/{institution_id}/grading-offerings/{subject_id}')
def apply(institution_id:uuid.UUID,subject_id:uuid.UUID,body:ApplyPolicy,db:Session=Depends(get_db),ctx:AuthContext=Depends(require_platform_admin)):
    institution=db.query(Institution).filter_by(id=institution_id).with_for_update().first()
    if not institution:raise HTTPException(404,'Institution not found')
    if institution.status==InstitutionStatus.ARCHIVED:raise HTTPException(409,'Archived institution cannot be changed')
    subject=db.query(Subject).filter_by(id=subject_id,institution_id=institution_id).first()
    if not subject:raise HTTPException(404,'Offering not found')
    group=db.get(AcademicClass,subject.class_id)
    writable_year(db,institution_id,group.academic_year)
    db.query(AcademicClass).filter_by(id=group.id).with_for_update().first()
    subject=db.query(Subject).filter_by(id=subject_id,institution_id=institution_id).with_for_update().populate_existing().one()
    def revision(value):
        try:
            timestamp=datetime.fromisoformat(value) if isinstance(value,str) else value
            return timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)
        except ValueError:return None
    if revision(subject.updated_at)!=revision(body.expected_subject_updated_at) or revision(institution.updated_at)!=revision(body.expected_institution_updated_at):
        raise HTTPException(409,'Policy or offering changed. Refresh before applying rules.')
    if body.confirmation!=subject.name:raise HTTPException(422,'Type the offering name to confirm recalculation')
    policy=academic_configuration(institution)['grading_rules']
    if not policy['enabled']:raise HTTPException(409,'Enable and save the institution grading policy first')
    subject.grading_policy=policy
    count=db.query(FinalGrade).filter_by(institution_id=institution_id,subject_id=subject_id).update({'released':False})
    db.query(CourseCompletion).filter(CourseCompletion.institution_id==institution_id,CourseCompletion.subject_id==subject_id,CourseCompletion.outcome!='EXEMPT').update({'released':False})
    record_audit(db,ctx,'grading_policy.applied_to_offering',subject_id,institution_id,f'{count} final results require review')
    commit(db)
    return dict(review_required=count)
