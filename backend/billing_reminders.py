"""Schedule hourly: python billing_reminders.py --send. Default is dry-run."""
import argparse
import json
from app.db.session import SessionLocal
from app.services.billing_reminders import send_billing_reminders


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="Deliver due notices to configured institution official emails")
    args = parser.parse_args()
    with SessionLocal() as db:
        result = send_billing_reminders(db, deliver=args.send)
    print(json.dumps({"dry_run": not args.send, **result}))
    raise SystemExit(1 if result["failed"] or result["missing_email"] else 0)
