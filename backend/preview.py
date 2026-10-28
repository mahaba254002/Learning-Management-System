"""Run a local-only preview using .env plus ignored .env.preview overrides."""
import os
from pathlib import Path
import uvicorn
from dotenv import load_dotenv
from sqlalchemy.engine import make_url


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    overrides = root / ".env.preview"
    if not overrides.is_file():
        raise SystemExit("Create backend/.env.preview with a local DATABASE_URL before starting the preview.")
    load_dotenv(root / ".env")
    load_dotenv(overrides, override=True)
    if make_url(os.environ.get("DATABASE_URL", "")).host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Preview startup refused: DATABASE_URL must point to local PostgreSQL.")
    os.chdir(root)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8010, forwarded_allow_ips="")
