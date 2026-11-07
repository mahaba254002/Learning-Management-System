"""Send parent messages still waiting in the outbox. Schedule hourly: python send_messages.py

Messages normally go out straight after the admin sends them; this picks up
anything interrupted, such as a provider outage or a restart."""
import json

from sqlalchemy import func

from app.api.routes.messaging import process
from app.db.session import SessionLocal, engine
from app.models.messaging import MessageDelivery


if __name__ == "__main__":
    with SessionLocal() as db:
        waiting = db.query(func.count(MessageDelivery.id)).filter(MessageDelivery.status == 'QUEUED').scalar()
    process(engine)
    with SessionLocal() as db:
        left = db.query(func.count(MessageDelivery.id)).filter(MessageDelivery.status == 'QUEUED').scalar()
    print(json.dumps({"waiting": waiting, "still_waiting": left}))
