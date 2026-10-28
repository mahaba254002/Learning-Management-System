from app.models.audit import AuditEvent


def record_audit(db, ctx, action, target_id, institution_id=None, detail=''):
    # Fixed descriptions only: never copy passwords, tokens or submission content.
    actor_id = ctx.actor_user_id or ctx.user_id
    if ctx.actor_user_id:
        detail = f"Acting as {ctx.user_id}. {detail}"[:500]
    db.add(AuditEvent(actor_id=actor_id, institution_id=institution_id,
                      action=action, target_id=str(target_id), detail=detail[:500],
                      ip_address=ctx.ip_address, request_method=ctx.request_method, request_path=ctx.request_path))
