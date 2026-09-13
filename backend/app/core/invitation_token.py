"""
Secure token generation for invitation links.

Concept note: unlike our 6-digit verification codes (short, human-typeable,
used alongside a known account), an invitation token is embedded directly
in a URL and needs to be long and unguessable on its own, since it's the
ONLY proof of identity for an anonymous person clicking a link — there's no
separate "account" to also check it against.
"""

import secrets


def generate_invite_token() -> str:
    # 32 bytes of randomness, URL-safe encoded — effectively unguessable.
    return secrets.token_urlsafe(32)