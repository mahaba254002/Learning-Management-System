"""Shared test settings, loaded before any test module imports the app.

The app defaults to production settings. Tests run over plain HTTP against
an in-memory database, so they opt into development explicitly."""
import os

os.environ.setdefault("ENVIRONMENT", "development")


import pytest  # noqa: E402


@pytest.fixture
def reports_enabled():
    """Report cards are off by default; tests of report cards switch them on for every institution they create."""
    from sqlalchemy import event
    from app.models.institution import Institution

    def enable(mapper, connection, target):
        target.module_settings = {**(target.module_settings or {}), 'academic_reports': True}

    event.listen(Institution, 'before_insert', enable)
    yield
    event.remove(Institution, 'before_insert', enable)
