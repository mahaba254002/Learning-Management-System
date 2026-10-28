"""Hierarchy checks shared by workspace entry and every delegated request."""
import uuid

from fastapi import HTTPException
from sqlalchemy import or_

from app.models.academic import AcademicClass, Enrollment, Student, Subject
from app.models.institution import Institution, InstitutionStatus
from app.models.teacher import Teacher, TeacherStatus
from app.models.user import User, UserRole, UserStatus
from app.models.pilot import AcademicYear
from app.models.curriculum import CourseRegistration


def resolve_workspace_target(db, actor: User, target_id: uuid.UUID):
    denied = HTTPException(404, "Workspace is not available to your account")
    target = db.get(User, target_id)
    if target is None or target.id == actor.id or target.status != UserStatus.ACTIVE:
        raise denied
    if target.role == UserRole.PLATFORM_ADMIN or target.institution_id is None:
        raise denied
    institution = db.get(Institution, target.institution_id)
    if institution is None or institution.status != InstitutionStatus.ACTIVE:
        raise denied
    from app.services.subscriptions import check_subscription_access
    if actor.role != UserRole.PLATFORM_ADMIN:
        check_subscription_access(db, target.institution_id)

    if actor.role == UserRole.PLATFORM_ADMIN:
        pass
    elif actor.role == UserRole.INSTITUTION_ADMIN:
        if target.institution_id != actor.institution_id or target.role not in {UserRole.TEACHER, UserRole.STUDENT}:
            raise denied
    elif actor.role == UserRole.TEACHER:
        if target.institution_id != actor.institution_id or target.role != UserRole.STUDENT:
            raise denied
        active_teacher = db.query(Teacher).filter_by(user_id=actor.id, institution_id=actor.institution_id,
                                                   status=TeacherStatus.ACTIVE).first()
        if active_teacher is None:
            raise denied
        profile = db.query(Student).filter_by(user_id=target.id, institution_id=actor.institution_id).first()
        registered = db.query(CourseRegistration.subject_id).filter_by(institution_id=actor.institution_id, student_id=profile.id if profile else None, active=True)
        taught = db.query(Subject.class_id).filter(Subject.institution_id == actor.institution_id, Subject.teacher_id == actor.id,
            or_(Subject.registration_mode == 'COHORT', Subject.id.in_(registered)))
        closed_years = db.query(AcademicYear.name).filter_by(institution_id=actor.institution_id, status='CLOSED')
        eligible = db.query(Student).join(Enrollment, Enrollment.student_id == Student.id).join(
            AcademicClass, AcademicClass.id == Enrollment.class_id).filter(
            Student.user_id == target.id, Student.institution_id == actor.institution_id,
            Enrollment.institution_id == actor.institution_id, Enrollment.active.is_(True),
            AcademicClass.institution_id == actor.institution_id,
            AcademicClass.academic_year.not_in(closed_years),
            or_(AcademicClass.supervisor_id == actor.id, AcademicClass.id.in_(taught)),
        ).first()
        if eligible is None:
            raise denied
    else:
        raise denied

    if target.role == UserRole.STUDENT:
        profile = db.query(Student).filter_by(user_id=target.id, institution_id=target.institution_id).first()
        if profile is None:
            raise denied
    elif target.role == UserRole.TEACHER:
        profile = db.query(Teacher).filter_by(user_id=target.id, institution_id=target.institution_id,
                                             status=TeacherStatus.ACTIVE).first()
        if profile is None:
            raise denied
    return target, actor.role != UserRole.PLATFORM_ADMIN
