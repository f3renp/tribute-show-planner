"""Tests for shows/service.py.

The first tests cover the pure functions (validate_show, validate_break,
move_in_order). The rest use the database fixture from conftest.py and
add songs through the catalogue service, the same way the app does.
"""
import pytest

from catalogue import repository as catalogue_repository
from catalogue import service as catalogue_service
from shows import repository, service


def valid_show_form():
    """A show form that passes every check."""
    return {
        "name": "Halloween night",
        "venue": "Teatro Real",
        "show_date": "2026-10-31",
        "max_minutes": "90",
    }


# Show and break validation ----------------------------------------------


def test_valid_show_has_no_errors_and_typed_values():
    show, errors = service.validate_show(valid_show_form())
    assert errors == []
    assert show["max_minutes"] == 90


def test_empty_show_form_reports_every_problem_at_once():
    show, errors = service.validate_show({})
    assert len(errors) == 4


@pytest.mark.parametrize(
    "field, value",
    [
        ("name", " "),
        ("venue", ""),
        ("show_date", "31/10/2026"),
        ("show_date", "2026-02-30"),
        ("max_minutes", "0"),
        ("max_minutes", "241"),
        ("max_minutes", "ninety"),
    ],
)
def test_one_bad_show_field_gives_exactly_one_error(field, value):
    form = dict(valid_show_form(), **{field: value})
    show, errors = service.validate_show(form)
    assert len(errors) == 1


def test_valid_break():
    form = {"break_label": " Costume change ", "break_seconds": "120"}
    assert service.validate_break(form) == ("Costume change", 120, [])


@pytest.mark.parametrize(
    "form",
    [
        {"break_label": "", "break_seconds": "120"},
        {"break_label": "Rest", "break_seconds": "0"},
        {"break_label": "Rest", "break_seconds": "1801"},
        {"break_label": "Rest", "break_seconds": "two"},
    ],
)
def test_bad_break_gives_one_error(form):
    label, seconds, errors = service.validate_break(form)
    assert len(errors) == 1


# Reordering -------------------------------------------------------------


def test_move_up_swaps_with_the_item_before():
    assert service.move_in_order([10, 20, 30], 30, "up") == [10, 30, 20]


def test_move_down_swaps_with_the_item_after():
    assert service.move_in_order([10, 20, 30], 10, "down") == [20, 10, 30]


def test_first_item_cannot_move_up_and_last_cannot_move_down():
    assert service.move_in_order([10, 20, 30], 10, "up") == [10, 20, 30]
    assert service.move_in_order([10, 20, 30], 30, "down") == [10, 20, 30]


def test_unknown_item_leaves_the_order_unchanged():
    assert service.move_in_order([10, 20], 99, "up") == [10, 20]


def test_move_in_order_does_not_change_the_list_it_is_given():
    item_ids = [10, 20, 30]
    service.move_in_order(item_ids, 30, "up")
    assert item_ids == [10, 20, 30]


def test_unknown_direction_raises():
    with pytest.raises(ValueError):
        service.move_in_order([10, 20], 10, "sideways")


# Saving and reading setlists (temporary database) -----------------------


def add_song(title, outfit_name="Red jacket"):
    """Save an outfit (if new) and a song through the catalogue. Return the song id."""
    if catalogue_repository.find_outfit_by_name(outfit_name) is None:
        catalogue_service.add_outfit({"name": outfit_name, "change_seconds": "90"})
    outfit_id = catalogue_repository.find_outfit_by_name(outfit_name)["id"]
    form = {
        "title": title,
        "album": "Thriller",
        "year": "1982",
        "duration": "4:54",
        "energy": "4",
        "kind": "dance",
        "outfit_id": str(outfit_id),
    }
    assert catalogue_service.add_song(form) == []
    return catalogue_repository.find_song_by_title_and_album(title, "Thriller")["id"]


def create_show():
    """Save a valid show and return its id."""
    show_id, errors = service.create_show(valid_show_form())
    assert errors == []
    return show_id


def item_labels(show_id):
    """The setlist as short labels in order, e.g. ["Billie Jean", "break: Rest"]."""
    labels = []
    for item in service.get_setlist(show_id):
        if item["item_type"] == "song":
            labels.append(item["song"]["title"])
        else:
            labels.append("break: " + item["break_label"])
    return labels


@pytest.mark.usefixtures("database")
def test_create_show_saves_it():
    show_id = create_show()
    assert repository.get_show(show_id)["venue"] == "Teatro Real"


@pytest.mark.usefixtures("database")
def test_create_show_with_errors_saves_nothing():
    show_id, errors = service.create_show(dict(valid_show_form(), name=""))
    assert show_id is None
    assert errors == ["Name is required."]
    assert repository.list_shows() == []


@pytest.mark.usefixtures("database")
def test_songs_and_breaks_are_added_at_the_end_in_order():
    show_id = create_show()
    assert service.add_song_to_setlist(show_id, add_song("Billie Jean")) == []
    form = {"break_label": "Rest", "break_seconds": "60"}
    assert service.add_break_to_setlist(show_id, form) == []
    assert service.add_song_to_setlist(show_id, add_song("Beat It")) == []
    assert item_labels(show_id) == ["Billie Jean", "break: Rest", "Beat It"]
    positions = [item["position"] for item in repository.list_items(show_id)]
    assert positions == [1, 2, 3]


@pytest.mark.usefixtures("database")
def test_get_setlist_attaches_the_catalogue_details():
    show_id = create_show()
    service.add_song_to_setlist(show_id, add_song("Billie Jean"))
    song = service.get_setlist(show_id)[0]["song"]
    assert song["duration_seconds"] == 294
    assert song["outfit_change_seconds"] == 90


@pytest.mark.usefixtures("database")
def test_add_song_to_setlist_refuses_no_song_missing_song_and_retired_song():
    show_id = create_show()
    song_id = add_song("Billie Jean")
    catalogue_service.retire_song(song_id)
    assert service.add_song_to_setlist(show_id, None) == ["Choose a song."]
    assert service.add_song_to_setlist(show_id, 99) == [
        "That song is not in the catalogue."
    ]
    assert service.add_song_to_setlist(show_id, song_id) == ["That song is retired."]
    assert repository.list_items(show_id) == []


@pytest.mark.usefixtures("database")
def test_bad_break_is_not_saved():
    show_id = create_show()
    errors = service.add_break_to_setlist(show_id, {"break_label": "", "break_seconds": "60"})
    assert errors == ["Break label is required."]
    assert repository.list_items(show_id) == []


@pytest.mark.usefixtures("database")
def test_retired_song_stays_in_an_existing_setlist():
    show_id = create_show()
    song_id = add_song("Billie Jean")
    service.add_song_to_setlist(show_id, song_id)
    catalogue_service.retire_song(song_id)
    setlist = service.get_setlist(show_id)
    assert setlist[0]["song"]["active"] == 0


@pytest.mark.usefixtures("database")
def test_move_item_saves_the_new_order():
    show_id = create_show()
    for title in ["Billie Jean", "Beat It", "Thriller"]:
        service.add_song_to_setlist(show_id, add_song(title))
    last_item_id = repository.list_items(show_id)[2]["id"]
    service.move_item(show_id, last_item_id, "up")
    assert item_labels(show_id) == ["Billie Jean", "Thriller", "Beat It"]


@pytest.mark.usefixtures("database")
def test_remove_item_closes_the_gap_in_positions():
    show_id = create_show()
    for title in ["Billie Jean", "Beat It", "Thriller"]:
        service.add_song_to_setlist(show_id, add_song(title))
    middle_item_id = repository.list_items(show_id)[1]["id"]
    service.remove_item(show_id, middle_item_id)
    assert item_labels(show_id) == ["Billie Jean", "Thriller"]
    positions = [item["position"] for item in repository.list_items(show_id)]
    assert positions == [1, 2]
