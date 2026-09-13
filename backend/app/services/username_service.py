"""
Username generation: {first_name}.{last_name}.{institution_code}, with
automatic numeric disambiguation on collision within that institution.

Concept note: this is intentionally a pure function (no side effects other
than the DB read to check collisions) so it's easy to test and reuse across
every account-creation path (institution admin, teacher, student) without
duplicating this logic in three places.
"""

import re

from sqlalchemy.orm import Session

from app.models.user import User


def _slugify_name_part(value: str) -> str:
    """Lowercase, strip anything that isn't a letter or digit.
    'O'Brien' -> 'obrien', 'Mary-Jane' -> 'maryjane'"""
    value = value.strip().lower()
    return re.sub(r"[^a-z0-9]", "", value)


def generate_username(*, db: Session, first_name: str, last_name: str, institution_code: str) -> str:
    first_slug = _slugify_name_part(first_name)
    last_slug = _slugify_name_part(last_name)

    if not first_slug or not last_slug:
        raise ValueError("First and last name must contain at least one letter or digit")

    base = f"{first_slug}.{last_slug}.{institution_code}"

    # Fast path: no collision at all — the common case.
    if db.query(User).filter(User.username == base).first() is None:
        return base

    # Collision within this institution: try appending 2, 3, 4... to the
    # first-name part until we find one that's free. Capped at a reasonable
    # limit so a bug elsewhere can't spin this into an infinite loop.
    for suffix in range(2, 1000):
        candidate = f"{first_slug}{suffix}.{last_slug}.{institution_code}"
        if db.query(User).filter(User.username == candidate).first() is None:
            return candidate

    raise RuntimeError("Could not generate a unique username after 1000 attempts")