"""Tests for the cleaning between tests in conftest.py: no rows are left and
ids start at 1 again, so every test starts from the same state."""
import pytest

import config
import db
from conftest import empty_tables


def add_outfit(name):
    return db.insert(
        "INSERT INTO outfits (name, change_seconds) OUTPUT INSERTED.id VALUES (%s, 60)",
        (name,),
    )


@pytest.mark.usefixtures("database")
def test_emptying_deletes_every_row_and_ids_start_at_1_again():
    add_outfit("Tuxedo")
    assert add_outfit("Sequin jacket") == 2
    empty_tables()
    assert db.fetch_all("SELECT id FROM outfits") == []
    assert add_outfit("Tuxedo") == 1


@pytest.mark.usefixtures("fresh_database")
def test_a_table_that_never_had_a_row_still_starts_at_1():
    # RESEED 0 on a brand-new table would make the first id 0.
    empty_tables()
    assert add_outfit("Tuxedo") == 1


def test_cleaning_refuses_a_database_not_named_test(monkeypatch):
    monkeypatch.setattr(
        config, "DATABASE_URL", "mssql://user:pw@127.0.0.1:1433/catalogue"
    )
    with pytest.raises(RuntimeError, match="Refusing"):
        empty_tables()
