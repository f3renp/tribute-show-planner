"""Versioned migrations: run the files in migrations/ in order, each once.

A migration is a file named NNN_what_it_does.sql (001_init.sql, ...). The
version (the file name without .sql) of every applied migration is stored
in the schema_migrations table, so a second start applies nothing.

Rules: an applied file is never edited (a correction is a new file with the
next number), and tables are never dropped to change them.
"""
import os
import re

import config
import db

# NNN_name.sql: three digits, so sorting the names gives the right order.
MIGRATION_FILE = re.compile(r"^\d{3}_\w+\.sql$")

# A line with only GO on it ends a batch. GO is not SQL: tools such as
# sqlcmd split on it, and so does this runner. Batches are needed when a
# statement uses something the previous one created, e.g. ALTER TABLE ...
# ADD a column, then UPDATE that column.
GO_LINE = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)

CREATE_MIGRATIONS_TABLE = """
IF OBJECT_ID(N'schema_migrations', N'U') IS NULL
    CREATE TABLE schema_migrations (
        version    NVARCHAR(100) NOT NULL PRIMARY KEY,
        applied_at DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
    );
"""


def split_batches(sql):
    """Split a migration's text on GO lines, leaving out empty batches."""
    return [batch.strip() for batch in GO_LINE.split(sql) if batch.strip()]


def migration_files(folder):
    """The migration file names in the folder, in the order they must run."""
    return sorted(name for name in os.listdir(folder) if MIGRATION_FILE.match(name))


def version_of(file_name):
    """001_init.sql -> 001_init"""
    return file_name.removesuffix(".sql")


def applied_versions(cursor):
    """The versions already recorded in schema_migrations."""
    cursor.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cursor.fetchall()}


def apply_one(connection, folder, file_name):
    """Run one migration and record it, in a single transaction.

    SQL Server can undo table changes (DDL) too, so if any batch fails the
    rollback leaves the database as it was before this file, unrecorded.
    """
    # utf-8-sig also reads files that an editor saved with a BOM.
    with open(os.path.join(folder, file_name), encoding="utf-8-sig") as file:
        batches = split_batches(file.read())
    cursor = connection.cursor()
    try:
        for batch in batches:
            cursor.execute(batch)
        cursor.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s)",
            (version_of(file_name),),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def apply_migrations(folder=None):
    """Apply every migration not applied yet, in order. Return their versions.

    Runs at startup, before the app serves requests. Azure runs at most one
    replica, so two copies never run this at the same time.
    """
    folder = folder or config.MIGRATIONS_DIR
    connection = db.get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(CREATE_MIGRATIONS_TABLE)
        connection.commit()
        already_applied = applied_versions(cursor)
        applied_now = []
        for file_name in migration_files(folder):
            if version_of(file_name) in already_applied:
                continue
            apply_one(connection, folder, file_name)
            db.log(f"migration applied: {file_name}")
            applied_now.append(version_of(file_name))
    finally:
        connection.close()
    if not applied_now:
        db.log("migrations: database is up to date")
    return applied_now
