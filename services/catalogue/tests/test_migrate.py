"""Tests for migrate.py: the files run in order, once each, and a failed
migration changes nothing."""
import pymssql
import pytest

import db
import migrate


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

@pytest.mark.usefixtures("database")
def test_the_first_start_applies_and_records_001():
    # The database fixture has just run the migrations on an empty database.
    assert recorded_versions() == ["001_init"]


@pytest.mark.usefixtures("database")
def test_a_second_start_applies_nothing():
    assert migrate.apply_migrations() == []
    assert recorded_versions() == ["001_init"]


@pytest.mark.usefixtures("database")
def test_a_new_migration_runs_once_and_keeps_existing_rows(tmp_path):
    db.insert(
        "INSERT INTO outfits (name, change_seconds) OUTPUT INSERTED.id VALUES (%s, %s)",
        ("Tuxedo", 90),
    )
    write_migration(
        tmp_path,
        "002_add_outfit_colour.sql",
        "ALTER TABLE outfits ADD colour NVARCHAR(20) NULL;\nGO\n"
        "UPDATE outfits SET colour = N'black';\n",
    )
    assert migrate.apply_migrations(tmp_path) == ["002_add_outfit_colour"]
    assert migrate.apply_migrations(tmp_path) == []
    outfit = db.fetch_one("SELECT name, colour FROM outfits")
    assert outfit == {"name": "Tuxedo", "colour": "black"}


@pytest.mark.usefixtures("database")
def test_a_failing_migration_is_rolled_back_and_not_recorded(tmp_path):
    write_migration(
        tmp_path,
        "002_broken.sql",
        "CREATE TABLE rollback_check (id INT);\nGO\nSELECT * FROM no_such_table;\n",
    )
    with pytest.raises(pymssql.Error):
        migrate.apply_migrations(tmp_path)
    assert recorded_versions() == ["001_init"]
    assert db.fetch_one("SELECT OBJECT_ID(N'rollback_check') AS id")["id"] is None
