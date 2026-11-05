"""Shared test settings, loaded before any test module imports the app.

The app defaults to production settings. Tests run over plain HTTP against
an in-memory database, so they opt into development explicitly."""
import os

os.environ.setdefault("ENVIRONMENT", "development")
