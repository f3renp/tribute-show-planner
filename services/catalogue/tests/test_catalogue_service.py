"""Tests for the catalogue functions that save and read through SQL Server.

Each test starts with an empty catalogue_test database (the database
fixture in conftest.py).
"""
import pytest

from catalogue import repository, service

# Every test in this file runs with the database fixture.
pytestmark = pytest.mark.usefixtures("database")


def add_outfit(name="Red jacket", change_seconds="90"):
    """Save an outfit and return its id."""
    outfit_id, errors = service.add_outfit({"name": name, "change_seconds": change_seconds})
    assert errors == []
    return outfit_id


def song_form(outfit_id, title="Billie Jean", album="Thriller"):
    """A valid song form for the given outfit."""
    return {
        "title": title,
        "album": album,
        "year": "1982",
        "duration": "4:54",
        "energy": "4",
        "kind": "dance",
        "outfit_id": str(outfit_id),
    }


def add_song(outfit_id, title="Billie Jean", album="Thriller"):
    """Save a song and return its id."""
    song_id, errors = service.add_song(song_form(outfit_id, title, album))
    assert errors == []
    return song_id


# Adding outfits ---------------------------------------------------------


def test_add_outfit_saves_it_and_returns_its_id():
    outfit_id = add_outfit("Red jacket", "90")
    assert repository.get_outfit(outfit_id)["name"] == "Red jacket"
    assert repository.get_outfit(outfit_id)["change_seconds"] == 90


def test_add_outfit_rejects_a_duplicate_name():
    add_outfit("Red jacket")
    result = service.add_outfit({"name": "Red jacket", "change_seconds": "30"})
    assert result == (None, ["An outfit with this name already exists."])
    assert len(repository.list_outfits()) == 1


def test_add_outfit_with_a_bad_form_saves_nothing():
    result = service.add_outfit({"name": "", "change_seconds": "90"})
    assert result == (None, ["Name is required."])
    assert repository.list_outfits() == []


# Editing and removing outfits -------------------------------------------


def test_edit_outfit_saves_the_changes():
    outfit_id = add_outfit("Red jacket", "90")
    form = {"name": "Red leather jacket", "change_seconds": "150"}
    assert service.edit_outfit(outfit_id, form) == []
    outfit = repository.get_outfit(outfit_id)
    assert outfit["name"] == "Red leather jacket"
    assert outfit["change_seconds"] == 150


def test_edit_outfit_may_keep_its_own_name():
    outfit_id = add_outfit("Red jacket", "90")
    form = {"name": "Red jacket", "change_seconds": "60"}
    assert service.edit_outfit(outfit_id, form) == []


def test_edit_outfit_rejects_another_outfits_name_and_saves_nothing():
    add_outfit("Tuxedo", "90")
    outfit_id = add_outfit("Red jacket", "90")
    form = {"name": "Tuxedo", "change_seconds": "30"}
    assert service.edit_outfit(outfit_id, form) == [
        "An outfit with this name already exists."
    ]
    assert repository.get_outfit(outfit_id)["change_seconds"] == 90


def test_edit_outfit_with_a_bad_form_saves_nothing():
    outfit_id = add_outfit("Red jacket", "90")
    form = {"name": "Red jacket", "change_seconds": str(service.MAX_CHANGE_SECONDS + 1)}
    assert service.edit_outfit(outfit_id, form) == [
        "Change time must be between 0 and 600 seconds."
    ]
    assert repository.get_outfit(outfit_id)["change_seconds"] == 90


def test_remove_outfit_no_song_uses_deletes_it():
    outfit_id = add_outfit()
    assert service.remove_outfit(outfit_id) == []
    assert repository.get_outfit(outfit_id) is None


def test_remove_outfit_used_by_a_song_is_refused_and_deletes_nothing():
    outfit_id = add_outfit()
    add_song(outfit_id)
    assert service.remove_outfit(outfit_id) == [
        "This outfit is used by 1 song (retired ones count too). "
        "Move them to another outfit first."
    ]
    assert repository.get_outfit(outfit_id) is not None


def test_remove_outfit_counts_retired_songs_too():
    outfit_id = add_outfit()
    service.retire_song(add_song(outfit_id, "Billie Jean"))
    add_song(outfit_id, "Beat It")
    [error] = service.remove_outfit(outfit_id)
    assert "used by 2 songs" in error


def test_outfit_song_count_includes_outfits_no_song_uses():
    used = add_outfit("Red jacket")
    add_outfit("Tuxedo")
    add_song(used)
    counts = {
        outfit["name"]: outfit["song_count"]
        for outfit in repository.list_outfits_with_song_count()
    }
    assert counts == {"Red jacket": 1, "Tuxedo": 0}


# Adding and editing songs -----------------------------------------------


def test_add_song_saves_typed_values_and_returns_its_id():
    song_id = add_song(add_outfit())
    song = repository.get_song(song_id)
    assert song["title"] == "Billie Jean"
    assert song["duration_seconds"] == 294
    assert song["active"] == 1


def test_add_song_with_a_bad_form_saves_nothing():
    form = dict(song_form(add_outfit()), energy="9")
    assert service.add_song(form) == (None, ["Energy must be between 1 and 5."])
    assert repository.list_songs() == []


def test_add_song_rejects_an_outfit_that_does_not_exist():
    _, errors = service.add_song(song_form(outfit_id=99))
    assert errors == ["That outfit does not exist."]


def test_add_song_rejects_the_same_title_and_album():
    outfit_id = add_outfit()
    add_song(outfit_id)
    _, errors = service.add_song(song_form(outfit_id))
    assert errors == ["This title and album is already in the catalogue."]


def test_same_title_on_another_album_is_allowed():
    outfit_id = add_outfit()
    add_song(outfit_id, "Billie Jean", "Thriller")
    add_song(outfit_id, "Billie Jean", "HIStory")
    assert len(repository.list_songs()) == 2


def test_edit_song_saves_the_changes():
    outfit_id = add_outfit()
    song_id = add_song(outfit_id)
    form = dict(song_form(outfit_id), duration="5:10")
    assert service.edit_song(song_id, form) == []
    assert repository.get_song(song_id)["duration_seconds"] == 310


def test_edit_song_is_not_a_duplicate_of_itself():
    outfit_id = add_outfit()
    song_id = add_song(outfit_id)
    assert service.edit_song(song_id, song_form(outfit_id)) == []


def test_edit_song_rejects_taking_another_songs_title_and_album():
    outfit_id = add_outfit()
    add_song(outfit_id, "Billie Jean", "Thriller")
    song_id = add_song(outfit_id, "Beat It", "Thriller")
    errors = service.edit_song(song_id, song_form(outfit_id, "Billie Jean", "Thriller"))
    assert errors == ["This title and album is already in the catalogue."]
    assert repository.get_song(song_id)["title"] == "Beat It"


# Retiring and the functions the show builder uses -----------------------


def test_retired_song_is_kept_but_not_active():
    outfit_id = add_outfit()
    song_id = add_song(outfit_id)
    service.retire_song(song_id)
    assert repository.get_song(song_id)["active"] == 0
    assert service.list_active_songs() == []


def test_reactivated_song_is_active_again():
    song_id = add_song(add_outfit())
    service.retire_song(song_id)
    service.reactivate_song(song_id)
    assert [song["id"] for song in service.list_active_songs()] == [song_id]


def test_get_songs_by_ids_includes_the_outfit_change_time():
    song_id = add_song(add_outfit("Red jacket", "90"))
    songs = service.get_songs_by_ids([song_id])
    assert songs[song_id]["outfit_name"] == "Red jacket"
    assert songs[song_id]["outfit_change_seconds"] == 90


def test_get_songs_by_ids_leaves_out_ids_that_do_not_exist():
    song_id = add_song(add_outfit())
    assert list(service.get_songs_by_ids([song_id, 99])) == [song_id]


def test_get_songs_by_ids_with_no_ids_is_empty():
    assert service.get_songs_by_ids([]) == {}
