"""Validate the teaching migration on an explicitly selected disposable database.

This deliberately refuses to run without both an explicit URL and a matching
expected host. Production is safe only with --read-only. The disposable mode
downgrades the schema and drops audit events on the selected database.
"""
import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config

BASE = "a3c4d5e6f7b8"
HEAD = "b4d5e6f7a8c9"
EXISTING_TABLES = {"academic_classes", "teaching_subjects", "students", "class_enrollments", "coursework", "student_scores", "student_attendance", "course_materials", "assignment_submissions"}
TABLES = EXISTING_TABLES | {"audit_events"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-host", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--confirm-disposable", action="store_true")
    mode.add_argument("--read-only", action="store_true", help="Inspect the current schema without running migrations")
    args = parser.parse_args()
    raw_url = os.environ.get("MIGRATION_TEST_DATABASE_URL")
    if not raw_url:
        raise RuntimeError("MIGRATION_TEST_DATABASE_URL must explicitly identify the target database")
    url = make_url(raw_url)
    if url.host != args.expected_host or "-pooler" in (url.host or ""):
        raise RuntimeError("Target must match the expected direct database host")
    engine = create_engine(url, connect_args={"connect_timeout": 15})
    os.environ["DATABASE_URL"] = raw_url
    os.environ["JWT_SECRET_KEY"] = "isolated-migration-validation-only"
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from app.db.base import Base
    from app.models import academic  # noqa: F401
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))

    def snapshot():
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            inspector = inspect(conn)
            columns = {col["name"] for col in inspector.get_columns("users")}
            counts = {table: conn.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()
                      for table in sorted(EXISTING_TABLES | {"users", "teachers", "institutions"})}
            revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            return columns, counts, revision

    before_columns, before_counts, revision = snapshot()
    if revision not in {BASE, HEAD}:
        raise RuntimeError("Unexpected starting migration revision")
    if not args.read_only:
        command.upgrade(config, HEAD)
        command.downgrade(config, BASE)
        command.upgrade(config, HEAD)
    after_columns, after_counts, revision = snapshot()
    assert revision == HEAD
    assert before_columns == after_columns
    assert before_counts == after_counts
    assert {"must_change_password", "password_changed_at"} <= after_columns
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        inspector = inspect(conn)
        assert TABLES <= set(inspector.get_table_names())
        for name in sorted(TABLES):
            expected = Base.metadata.tables[name]
            actual_columns = {c["name"]: c for c in inspector.get_columns(name)}
            assert set(actual_columns) == set(expected.columns.keys()), name
            for column in expected.columns:
                actual = actual_columns[column.name]
                assert actual["nullable"] == column.nullable, f"{name}.{column.name}: nullability"
                assert str(actual["type"].compile(dialect=engine.dialect)) == str(column.type.compile(dialect=engine.dialect)), f"{name}.{column.name}: type"
            expected_foreign_keys = {tuple((fk.parent.name, fk.column.table.name, fk.column.name) for fk in constraint.elements)
                                     for constraint in expected.foreign_key_constraints}
            actual_foreign_keys = {tuple((col, fk["referred_table"], ref) for col, ref in zip(fk["constrained_columns"], fk["referred_columns"])) for fk in inspector.get_foreign_keys(name)}
            assert actual_foreign_keys == expected_foreign_keys, f"{name}: foreign keys"
            from sqlalchemy import UniqueConstraint
            expected_unique = {tuple(col.name for col in constraint.columns) for constraint in expected.constraints if isinstance(constraint, UniqueConstraint)}
            actual_unique = {tuple(item["column_names"]) for item in inspector.get_unique_constraints(name)}
            assert actual_unique == expected_unique, f"{name}: uniqueness constraints"
            expected_indexes = {tuple(col.name for col in index.columns) for index in expected.indexes}
            actual_indexes = {tuple(index["column_names"]) for index in inspector.get_indexes(name) if not index.get("duplicates_constraint")}
            assert actual_indexes == expected_indexes, f"{name}: indexes"
        assert any(tuple(c["column_names"]) == ("institution_id", "id") for c in inspector.get_unique_constraints("users"))
    print("PASS: Read-only PostgreSQL schema verification" if args.read_only else "PASS: PostgreSQL downgrade and upgrade completed")
    if not args.read_only:
        print("PASS: Existing users, teachers and institutions preserved")
    print("PASS: All ten academic and administration tables match model columns, types, foreign keys, uniqueness and indexes")
    print("PASS: must_change_password and password_changed_at preserved")
    engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Driver exception text can contain connection details; do not print it.
        print(f"Migration validation failed ({type(error).__name__})", file=sys.stderr)
        raise SystemExit(1)
