"""Hash-chained payment evidence: reminders, prompts, callbacks and applied payments."""
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text

from app.models.subscription import PaymentMessage

GENESIS = "0" * 64
LOCK_KEY = 4747001


def _canonical(row):
    stamp = row.created_at
    if stamp.tzinfo:
        stamp = stamp.astimezone(timezone.utc).replace(tzinfo=None)
    return json.dumps(dict(sequence=row.sequence, created_at=stamp.isoformat(), institution_id=str(row.institution_id) if row.institution_id else None,
                           kind=row.kind, direction=row.direction, reference=row.reference, amount=str(row.amount) if row.amount is not None else None,
                           summary=row.summary, payload=row.payload), sort_keys=True, separators=(",", ":"), default=str)


def entry_hash(row):
    return hashlib.sha256((row.previous_hash + _canonical(row)).encode()).hexdigest()


def record_message(db, *, kind, direction, summary, institution_id=None, reference="", amount=None, payload=None):
    """Adds an entry inside the caller's transaction; the caller commits."""
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_KEY})
    last = db.query(PaymentMessage).order_by(PaymentMessage.sequence.desc()).first()
    row = PaymentMessage(sequence=(last.sequence + 1) if last else 1, created_at=datetime.now(timezone.utc).replace(microsecond=0),
                         institution_id=institution_id, kind=kind, direction=direction, reference=(reference or "")[:100],
                         amount=Decimal(str(amount)).quantize(Decimal("0.01")) if amount is not None else None, summary=summary,
                         payload=json.loads(json.dumps(payload or {}, default=str)), previous_hash=last.entry_hash if last else GENESIS)
    row.entry_hash = entry_hash(row)
    db.add(row)
    db.flush()
    return row


def verify_chain(db):
    previous, checked = GENESIS, 0
    for row in db.query(PaymentMessage).order_by(PaymentMessage.sequence).yield_per(500):
        checked += 1
        if row.sequence != checked or row.previous_hash != previous or entry_hash(row) != row.entry_hash:
            return dict(intact=False, checked=checked, first_broken_sequence=row.sequence)
        previous = row.entry_hash
    return dict(intact=True, checked=checked, first_broken_sequence=None)
