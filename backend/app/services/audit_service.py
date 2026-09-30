from app.models.audit import AuditEvent


def record_audit(db, ctx, action, target_id, institution_id=None, detail=''):
    # Fixed descriptions only: never copy passwords, tokens or submission content.
    db.add(AuditEvent(actor_id=ctx.user_id, institution_id=institution_id,
                      action=action, target_id=str(target_id), detail=detail))
