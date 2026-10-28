import uuid
import hashlib
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import AuthContext, require_tenant_user
from app.db.session import get_db
from app.models.academic import AcademicClass, Enrollment, Student
from app.models.academic_document import AcademicDocument
from app.models.pilot import AcademicPeriod, AcademicYear
from app.models.user import User, UserRole
from app.schemas.academic import Input
from app.api.routes.teaching import admin, staff, ensure_staff, scoped
from app.services import academic_documents as documents
from app.services.audit_service import record_audit

router=APIRouter(prefix='/api/academic-documents',tags=['Academic documents'])
Kind=Literal['REPORT_CARD','TRANSCRIPT']


class IssueInput(Input):
    student_id: uuid.UUID
    kind: Kind
    class_id: uuid.UUID | None = None
    period_id: uuid.UUID | None = None
    remarks: str = Field(default='',max_length=3000)
    expected_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class RevokeInput(Input):
    reason: str = Field(min_length=5,max_length=1000)


def summary(row):
    return dict(id=row.id,reference=row.reference,kind=row.kind,status=row.status,student_id=row.student_id,
        title=row.snapshot['title'],learner=row.snapshot['learner'],period=row.snapshot['period'],issued_at=row.created_at,
        issued_by=row.issued_by_name,revoked_at=row.revoked_at,revocation_reason=row.revocation_reason)


@router.get('/options')
def options(class_id: uuid.UUID | None=None,db:Session=Depends(get_db),ctx:AuthContext=Depends(staff)):
    ensure_staff(db,ctx)
    query=scoped(db,AcademicClass,ctx)
    if ctx.role==UserRole.TEACHER: query=query.filter_by(supervisor_id=ctx.user_id)
    groups=query.order_by(AcademicClass.academic_year.desc(),AcademicClass.name).all()
    if class_id and class_id not in {g.id for g in groups}: raise HTTPException(404,'Teaching group not found')
    people=[]; periods=[]
    if class_id:
        people=[dict(id=s.id,name=f'{u.first_name} {u.last_name}',admission_number=s.admission_number)
            for s,u in scoped(db,Student,ctx).add_entity(User).join(User,User.id==Student.user_id).join(Enrollment,Enrollment.student_id==Student.id).filter(
                Enrollment.institution_id==ctx.institution_id,Enrollment.class_id==class_id).order_by(User.first_name,User.last_name).all()]
        group=next(g for g in groups if g.id==class_id)
        year=scoped(db,AcademicYear,ctx).filter_by(name=group.academic_year).first()
        if year: periods=[dict(id=p.id,name=p.name) for p in scoped(db,AcademicPeriod,ctx).filter_by(year_id=year.id).order_by(AcademicPeriod.start_date).all()]
    return dict(groups=[dict(id=g.id,name=g.name,year=g.academic_year) for g in groups],students=people,periods=periods)


@router.get('/preview')
def preview(student_id:uuid.UUID,kind:Kind,class_id:uuid.UUID|None=None,period_id:uuid.UUID|None=None,
            db:Session=Depends(get_db),ctx:AuthContext=Depends(staff)):
    with documents.consistent_session(db) as snapshot:
        return documents.build(snapshot,ctx,student_id,kind,class_id,period_id)


@router.post('',status_code=201)
def issue(body:IssueInput,db:Session=Depends(get_db),ctx:AuthContext=Depends(admin)):
    with documents.consistent_session(db) as transaction:
        data=documents.build(transaction,ctx,body.student_id,body.kind,body.class_id,body.period_id)
        if data['source_digest']!=body.expected_digest: raise HTTPException(409,'Academic records changed. Preview and review the document again.')
        if not data['ready']: raise HTTPException(409,'Resolve the report readiness issues before issuing this document.')
        data['snapshot']['remarks']=body.remarks.strip()
        data['source_digest']=hashlib.sha256((data['source_digest']+'\n'+body.remarks.strip()).encode()).hexdigest()
        prior=scoped(transaction,AcademicDocument,ctx).filter_by(student_id=body.student_id,kind=body.kind,source_digest=data['source_digest']).first()
        if prior: raise HTTPException(409,'This exact document has already been issued. Open its history; change the remarks to identify a corrected reissue if necessary.')
        actor=transaction.get(User,ctx.actor_user_id or ctx.user_id)
        row=AcademicDocument(institution_id=ctx.institution_id,student_id=body.student_id,class_id=body.class_id,kind=body.kind,
            reference=f"{'RC' if body.kind=='REPORT_CARD' else 'TR'}-{uuid.uuid4().hex.upper()}",source_digest=data['source_digest'],
            snapshot=data['snapshot'],issued_by_name=f'{actor.first_name} {actor.last_name}')
        transaction.add(row)
        try:
            transaction.flush()
            record_audit(transaction,ctx,'academic_document.issued',row.id,ctx.institution_id,body.kind)
            transaction.commit()
        except IntegrityError:
            transaction.rollback(); raise HTTPException(409,'This document was issued in another session. Reload the history.')
        return dict(**summary(row),snapshot=row.snapshot)


@router.get('')
def listing(student_id:uuid.UUID|None=None,class_id:uuid.UUID|None=None,offset:int=Query(0,ge=0),db:Session=Depends(get_db),ctx:AuthContext=Depends(require_tenant_user)):
    q=scoped(db,AcademicDocument,ctx)
    if ctx.role==UserRole.STUDENT:
        own=scoped(db,Student,ctx).filter_by(user_id=ctx.user_id).first()
        if not own: raise HTTPException(404,'Learner not found')
        q=q.filter_by(student_id=own.id,status='ISSUED')
    else:
        ensure_staff(db,ctx)
        if ctx.role==UserRole.TEACHER:
            groups=scoped(db,AcademicClass,ctx).filter_by(supervisor_id=ctx.user_id).with_entities(AcademicClass.id)
            q=q.filter(AcademicDocument.class_id.in_(groups))
        if student_id: q=q.filter_by(student_id=student_id)
        if class_id: q=q.filter_by(class_id=class_id)
    return dict(total=q.count(),items=[summary(r) for r in q.order_by(AcademicDocument.created_at.desc(),AcademicDocument.id).offset(offset).limit(30).all()])


@router.get('/{document_id}')
def detail(document_id:uuid.UUID,db:Session=Depends(get_db),ctx:AuthContext=Depends(require_tenant_user)):
    row=scoped(db,AcademicDocument,ctx).filter_by(id=document_id).first()
    if not row: raise HTTPException(404,'Document not found')
    if ctx.role==UserRole.STUDENT:
        student=scoped(db,Student,ctx).filter_by(user_id=ctx.user_id).first()
        if not student or row.student_id!=student.id or row.status!='ISSUED': raise HTTPException(404,'Document not found')
    else:
        ensure_staff(db,ctx)
        if ctx.role==UserRole.TEACHER and not scoped(db,AcademicClass,ctx).filter_by(id=row.class_id,supervisor_id=ctx.user_id).first():
            raise HTTPException(404,'Document not found')
    return dict(**summary(row),snapshot=row.snapshot)


@router.post('/{document_id}/revoke')
def revoke(document_id:uuid.UUID,body:RevokeInput,db:Session=Depends(get_db),ctx:AuthContext=Depends(admin)):
    row=scoped(db,AcademicDocument,ctx).filter_by(id=document_id).with_for_update().first()
    if not row: raise HTTPException(404,'Document not found')
    if row.status!='ISSUED': raise HTTPException(409,'Document is already revoked')
    if not body.reason.strip(): raise HTTPException(422,'Give a reason for revocation')
    row.status='REVOKED'; row.revoked_at=datetime.now(timezone.utc); row.revocation_reason=body.reason.strip()
    record_audit(db,ctx,'academic_document.revoked',row.id,ctx.institution_id)
    db.commit()
    return summary(row)
