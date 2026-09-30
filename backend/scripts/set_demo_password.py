"""Privately set passwords for known demo accounts on an explicitly chosen host.

Uses the existing root .env.local direct connection; never prints credentials.
"""
import argparse
import os
import sys
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy.engine import make_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-host', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    raw = dotenv_values(root / '.env.local').get('DATABASE_URL_UNPOOLED')
    if not raw:
        raise ValueError('Root .env.local must contain DATABASE_URL_UNPOOLED')
    url = make_url(raw).set(drivername='postgresql+psycopg')
    if url.host != args.expected_host:
        raise ValueError('Configured host does not match the requested host')
    os.environ['SEED_DATABASE_URL'] = url.render_as_string(hide_password=False)
    import seed_demo
    sys.argv = [sys.argv[0], '--expected-host', args.expected_host, '--apply', '--set-demo-password']
    seed_demo.main()


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(f'Demo password setup failed ({type(error).__name__}). No credentials were printed.', file=sys.stderr)
        raise SystemExit(1)
