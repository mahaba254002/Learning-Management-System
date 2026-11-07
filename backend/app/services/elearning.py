"""Shared e-learning helpers: attaching uploaded files and in-app notifications."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.models.elearning import Notification, StoredFile
from app.services import storage

NAIROBI = ZoneInfo('Africa/Nairobi')


def file_view(row):
    if row is None:
        return None
    return dict(id=row.id, filename=row.filename, size_bytes=row.size_bytes, content_type=row.content_type)


def files_by_id(db, institution_id, ids):
    ids = [i for i in ids if i]
    if not ids:
        return {}
    return {f.id: f for f in db.query(StoredFile).filter(StoredFile.institution_id == institution_id, StoredFile.id.in_(ids),
                                                         StoredFile.deleted_at.is_(None)).all()}


def attachable(db, institution_id, file_id, *, purpose, subject_id, uploaded_by, student_id=None):
    """Check a file someone uploaded may be attached here. Returns the row, or None for no file."""
    if file_id is None:
        return None
    row = db.query(StoredFile).filter_by(institution_id=institution_id, id=file_id).first()
    if (row is None or row.deleted_at is not None or row.purpose != purpose or row.subject_id != subject_id
            or row.uploaded_by != uploaded_by or (student_id is not None and row.student_id != student_id)):
        raise HTTPException(422, 'That file is not available here. Upload it again.')
    return row


def replace_file(db, institution_id, old_id, new_id):
    """Remove a file that is no longer attached after an edit."""
    if old_id and old_id != new_id:
        row = db.query(StoredFile).filter_by(institution_id=institution_id, id=old_id).first()
        if row is not None and row.deleted_at is None:
            row.deleted_at = datetime.now(timezone.utc)
            storage.delete(row.storage_key)


def notify(db, institution_id, user_ids, ref, title, body='', link=''):
    """Add an in-app notification for each person, once per event (ref)."""
    user_ids = set(user_ids)
    if not user_ids:
        return
    seen = {u for (u,) in db.query(Notification.user_id).filter(Notification.ref == ref, Notification.user_id.in_(user_ids)).all()}
    for user_id in user_ids - seen:
        db.add(Notification(institution_id=institution_id, user_id=user_id, ref=ref, title=title[:200], body=body[:500], link=link[:300]))


def subject_user_ids(db, subject, ctx):
    from app.api.routes.teaching import subject_students
    return [u.id for _, u in subject_students(db, subject, ctx).all()]


def work_label(work):
    return 'quiz' if work.delivery == 'QUIZ' else {'EXAM': 'exam', 'COURSEWORK': 'CAT'}.get(work.kind, 'assignment')


def notify_work_published(db, ctx, work, subject):
    link = f'/student/quizzes/{work.id}' if work.delivery == 'QUIZ' else f'/student/assignments/{work.id}'
    from app.services.quiz import utc
    due = f"Due {utc(work.due_at).astimezone(NAIROBI):%a %d %b, %H:%M}." if work.due_at else ''
    notify(db, ctx.institution_id, subject_user_ids(db, subject, ctx), f'work:{work.id}',
           f'New {work_label(work)} in {subject.name}: {work.title}', due, link)


def notify_material_published(db, ctx, material, subject):
    notify(db, ctx.institution_id, subject_user_ids(db, subject, ctx), f'material:{material.id}',
           f'New material in {subject.name}: {material.title}', '', f'/student/courses/{subject.id}')


def notify_results_released(db, ctx, work, subject, student_user_ids):
    notify(db, ctx.institution_id, student_user_ids, f'results:{work.id}',
           f'Marks released for {work.title}', subject.name, '/student/grades')
