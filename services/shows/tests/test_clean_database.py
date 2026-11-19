"""Tests for the cleaning between tests in conftest.py: no rows are left and
ids start at 1 again, so every test starts from the same state."""
import pytest

import config
import db
from conftest import empty_tables


def add_show(name):
    return db.insert(
        "INSERT INTO shows (name, venue, show_date, max_minutes) OUTPUT INSERTED.id "
        "VALUES (%s, N'Teatro Real', '2026-10-31', 90)",
        (name,),
    )


def add_break(show_id):
    return db.insert(
        "INSERT INTO setlist_items (show_id, position, item_type, break_label, break_seconds) "
        "OUTPUT INSERTED.id VALUES (%s, 1, N'break', N'Rest', 60)",
        (show_id,),
    )


@pytest.mark.usefixtures("database")
def test_emptying_deletes_every_row_and_ids_start_at_1_again():
    add_show("Halloween night")
    show_id = add_show("New Year's Eve")
    assert show_id == 2
    add_break(show_id)
    empty_tables()
    assert db.fetch_all("SELECT id FROM shows") == []
    assert db.fetch_all("SELECT id FROM setlist_items") == []
    new_show_id = add_show("Halloween night")
    assert new_show_id == 1
    assert add_break(new_show_id) == 1


@pytest.mark.usefixtures("fresh_database")
def test_a_table_that_never_had_a_row_still_starts_at_1():
    # RESEED 0 on a brand-new table would make the first id 0.
    empty_tables()
    assert add_show("Halloween night") == 1


def test_cleaning_refuses_a_database_not_named_test(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", "mssql://user:pw@127.0.0.1:1433/shows")
    with pytest.raises(RuntimeError, match="Refusing"):
        empty_tables()
