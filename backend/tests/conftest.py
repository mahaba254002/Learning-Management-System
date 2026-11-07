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


@pytest.fixture(autouse=True)
def platform_secret_passes(request, monkeypatch):
    """Most tests are about what an action does, not the secret question in front of it.
    Tests marked `real_secret` exercise the question itself."""
    if request.node.get_closest_marker('real_secret'):
        return
    from app.services import platform_secret
    monkeypatch.setattr(platform_secret, 'check', lambda db, ctx, answer, action: None)


def pytest_configure(config):
    config.addinivalue_line('markers', 'real_secret: run the platform secret question for real')
