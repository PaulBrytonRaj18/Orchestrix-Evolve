"""Decouple user_id columns from the legacy local users table.

Users are authenticated by Supabase and live in ``auth.users``; they are never
inserted into the app's ``users`` table, so the old FKs made every INSERT into
``sessions`` / ``scheduled_digests`` fail on Postgres.

Revision ID: 002_decouple_user_fk
Revises: 001_initial
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002_decouple_user_fk"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("sessions", "scheduled_digests")


def _user_fk_names(table: str) -> list[str]:
    insp = sa.inspect(op.get_bind())
    return [
        fk["name"]
        for fk in insp.get_foreign_keys(table)
        if fk.get("referred_table") == "users" and fk.get("name")
    ]


# SQLite reflects FKs without names; this convention names them so batch mode can drop them.
_SQLITE_FK_NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def upgrade() -> None:
    sqlite = op.get_bind().dialect.name == "sqlite"
    for table in _TABLES:
        if sqlite:
            with op.batch_alter_table(table, naming_convention=_SQLITE_FK_NAMING) as batch:
                batch.drop_constraint(f"fk_{table}_user_id_users", type_="foreignkey")
            continue
        names = _user_fk_names(table)
        if not names:
            continue
        with op.batch_alter_table(table) as batch:
            for name in names:
                batch.drop_constraint(name, type_="foreignkey")


def downgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(f"{table}_user_id_fkey", "users", ["user_id"], ["id"])
