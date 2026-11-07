"""Keep callback secrets out of logs.

M-Pesa and Africa's Talking callbacks carry a secret in the URL path, because
those providers do not sign their requests. Access logs and error logs would
otherwise record it, and anyone reading the logs could forge payments."""
import logging
import re

SECRET_PATHS = re.compile(r'(/api/(?:billing/)?payments/mpesa/|/api/messaging/at/|/mpesa/)[^/\s"?]+')


def redact(text):
    return SECRET_PATHS.sub(r'\1[redacted]', text)


class RedactSecrets(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


def install():
    for name in ('uvicorn.access', 'uvicorn.error', 'app.errors', ''):
        logging.getLogger(name).addFilter(RedactSecrets())
