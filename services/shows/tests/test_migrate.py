"""Tests for migrate.py: the files run in order, once each, and a failed
migration changes nothing. Then the real migrations: 002 keeps every row
that 001's tables already held."""
import shutil
from pathlib import Path

import pymssql
import pytest

import config
import db
import migrate
from conftest import drop_all_tables

# Every migration in migrations/, in order. Update it with each new file.
ALL_VERSIONS = ["001_init", "002_add_show_status"]


def recorded_versions():
    rows = db.fetch_all("SELECT version FROM schema_migrations ORDER BY version")
    return [row["version"] for row in rows]


def write_migration(folder, name, sql):
    (folder / name).write_text(sql, encoding="utf-8")


# Pure functions: no database ----------------------------------------------


def test_split_batches_splits_on_lines_that_are_only_go():
    sql = "CREATE TABLE a (id INT)\nGO\nSELECT 'GOOD'\n  go  \n\nGO\n"
    assert migrate.split_batches(sql) == ["CREATE TABLE a (id INT)", "SELECT 'GOOD'"]


def test_migration_files_are_sorted_and_other_files_are_ignored(tmp_path):
    for name in ["010_later.sql", "002_second.sql", "001_init.sql", "notes.txt", "3_bad.sql"]:
        write_migration(tmp_path, name, "")
    assert migrate.migration_files(tmp_path) == [
        "001_init.sql",
        "002_second.sql",
        "010_later.sql",
    ]


def test_version_is_the_file_name_without_sql():
    assert migrate.version_of("001_init.sql") == "001_init"


# Against the test database -------------------------------------------------
# fresh_database (conftest.py) drops every table and runs the migrations
# from 001 before each of these tests, and has the next test rebuild the
# schema, since the temporary 002 files below change it.

@pytest.mark.usefixtures("fresh_database")
def test_the_first_start_applies_and_records_every_migration():
    # The fixture has just run the migrations on an empty database.
    assert recorded_versions() == ALL_VERSIONS


@pytest.mark.usefixtures("fresh_database")
def test_a_second_start_applies_nothing():
    assert migrate.apply_migrations() == []
    assert recorded_versions() == ALL_VERSIONS


@pytest.mark.usefixtures("fresh_database")
def test_a_new_migration_runs_once_and_keeps_existing_rows(tmp_path):
    db.insert(
        "INSERT INTO shows (name, venue, show_date, max_minutes) OUTPUT INSERTED.id "
        "VALUES (%s, %s, %s, %s)",
        ("Halloween night", "Teatro Real", "2026-10-31", 90),
    )
    write_migration(
        tmp_path,
        "002_add_show_city.sql",
        "ALTER TABLE shows ADD city NVARCHAR(50) NULL;\nGO\n"
        "UPDATE shows SET city = N'Madrid';\n",
    )
    assert migrate.apply_migrations(tmp_path) == ["002_add_show_city"]
    assert migrate.apply_migrations(tmp_path) == []
    show = db.fetch_one("SELECT name, city FROM shows")
    assert show == {"name": "Halloween night", "city": "Madrid"}


@pytest.mark.usefixtures("fresh_database")
def test_a_failing_migration_is_rolled_back_and_not_recorded(tmp_path):
    write_migration(
        tmp_path,
        "002_broken.sql",
        "CREATE TABLE rollback_check (id INT);\nGO\nSELECT * FROM no_such_table;\n",
    )
    with pytest.raises(pymssql.Error):
        migrate.apply_migrations(tmp_path)
    assert recorded_versions() == ALL_VERSIONS
    assert db.fetch_one("SELECT OBJECT_ID(N'rollback_check') AS id")["id"] is None


# The real 002 on a database that already holds data ------------------------
# These start from an empty database, apply only 001 (as on Azure before
# the deploy), save a show with a setlist, and then apply 002.


def copy_migration(folder, file_name):
    """Copy one real migration from migrations/ into folder."""
    shutil.copy(Path(config.MIGRATIONS_DIR) / file_name, folder / file_name)


def database_at_001_with_a_show(folder):
    """An empty database with only 001 applied, holding one show with
    three songs and a break, like the one on Azure. Return the show id."""
    drop_all_tables()
    copy_migration(folder, "001_init.sql")
    assert migrate.apply_migrations(folder) == ["001_init"]
    show_id = db.insert(
        "INSERT INTO shows (name, venue, show_date, max_minutes) OUTPUT INSERTED.id "
        "VALUES (%s, %s, %s, %s)",
        ("christmas night", "Teatro Real", "2026-12-24", 90),
    )
    for position, song_id in [(1, 3), (2, 8), (4, 12)]:
        db.execute(
            "INSERT INTO setlist_items (show_id, position, item_type, song_id) "
            "VALUES (%s, %s, N'song', %s)",
            (show_id, position, song_id),
        )
    db.execute(
        "INSERT INTO setlist_items (show_id, position, item_type, break_label, break_seconds) "
        "VALUES (%s, 3, N'break', N'Costume change', 120)",
        (show_id,),
    )
    return show_id


def setlist_rows(show_id):
    return db.fetch_all(
        "SELECT id, position, item_type, song_id, break_label, break_seconds "
        "FROM setlist_items WHERE show_id = %s ORDER BY position",
        (show_id,),
    )


@pytest.mark.usefixtures("fresh_database")
def test_002_keeps_every_row_and_makes_existing_shows_planned(tmp_path):
    show_id = database_at_001_with_a_show(tmp_path)
    show_before = db.fetch_one("SELECT * FROM shows WHERE id = %s", (show_id,))
    setlist_before = setlist_rows(show_id)

    copy_migration(tmp_path, "002_add_show_status.sql")
    assert migrate.apply_migrations(tmp_path) == ["002_add_show_status"]

    show_after = db.fetch_one("SELECT * FROM shows WHERE id = %s", (show_id,))
    # The same row, with every old value unchanged, plus the new column.
    assert show_after == dict(show_before, status="planned")
    assert setlist_rows(show_id) == setlist_before
    assert len(setlist_before) == 4
    assert recorded_versions() == ALL_VERSIONS


@pytest.mark.usefixtures("fresh_database")
def test_after_002_the_previous_images_insert_still_works(tmp_path):
    # While a deploy runs, the old revision can still save a show with the
    # INSERT it knows, which does not name status.
    database_at_001_with_a_show(tmp_path)
    copy_migration(tmp_path, "002_add_show_status.sql")
    migrate.apply_migrations(tmp_path)
    show_id = db.insert(
        "INSERT INTO shows (name, venue, show_date, max_minutes) OUTPUT INSERTED.id "
        "VALUES (%s, %s, %s, %s)",
        ("New year", "Sala Apolo", "2026-12-31", 60),
    )
    assert db.fetch_one("SELECT status FROM shows WHERE id = %s", (show_id,)) == {
        "status": "planned"
    }


@pytest.mark.usefixtures("database")
def test_the_database_refuses_an_unknown_status():
    # ck_shows_status guards the column even if the validation is bypassed.
    with pytest.raises(pymssql.IntegrityError):
        db.execute(
            "INSERT INTO shows (name, venue, show_date, max_minutes, status) "
            "VALUES (N'x', N'y', '2026-10-31', 90, N'sold out')"
        )
