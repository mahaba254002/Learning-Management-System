from fastapi import HTTPException
from app.models.pilot import AcademicYear


def writable_year(db, institution_id, name):
    year = db.query(AcademicYear).filter_by(institution_id=institution_id, name=name).with_for_update().first()
    if year and year.status == 'CLOSED':
        raise HTTPException(409, 'This academic year is closed. Its academic records are read-only.')
    return year
