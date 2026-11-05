"""The one place that limits queries to the caller's institution.

Every tenant-owned table carries institution_id, backed by composite
(institution_id, id) foreign keys. Route code must load tenant records
through these helpers so a record from another institution is always
reported as not found, never returned.
"""
from fastapi import HTTPException


def scoped(db, model, ctx):
    """Query for model rows that belong to the caller's institution."""
    return db.query(model).filter(model.institution_id == ctx.institution_id)


def owned(db, model, identity, tenant, *, lock=False, not_found="Record not found"):
    """Load one row by id within an institution, or raise 404.

    Returns None when identity is None, so optional references stay optional."""
    if identity is None:
        return None
    query = db.query(model).filter_by(id=identity, institution_id=tenant)
    row = (query.with_for_update() if lock else query).first()
    if row is None:
        raise HTTPException(404, not_found)
    return row
