"""Unit tests for the setlist checks in shows/rules.py: no database, no Flask."""
from shows.rules import (
    check_outfit_changes,
    check_running_time,
    format_duration,
    setlist_seconds,
)


def song_item(position, title, duration=240, outfit_id=1, change_seconds=0):
    """A song item shaped like the ones service.get_setlist returns."""
    return {
        "position": position,
        "item_type": "song",
        "song_id": position,
        "song": {
            "id": position,
            "title": title,
            "duration_seconds": duration,
            "outfit_id": outfit_id,
            "outfit_name": f"Outfit {outfit_id}",
            "outfit_change_seconds": change_seconds,
        },
    }


def break_item(position, seconds):
    """A break item shaped like the ones service.get_setlist returns."""
    return {
        "position": position,
        "item_type": "break",
        "song_id": None,
        "song": None,
        "break_label": "Break",
        "break_seconds": seconds,
    }


def missing_song_item(position):
    """A song item whose id is no longer in the catalogue."""
    return {"position": position, "item_type": "song", "song_id": 99, "song": None}


# Running time -----------------------------------------------------------


def test_format_duration():
    assert format_duration(294) == "4:54"
    assert format_duration(5) == "0:05"


def test_setlist_seconds_adds_songs_and_breaks():
    items = [song_item(1, "Thriller", duration=300), break_item(2, 60)]
    assert setlist_seconds(items) == 360


def test_setlist_seconds_skips_missing_songs():
    items = [song_item(1, "Thriller", duration=300), missing_song_item(2)]
    assert setlist_seconds(items) == 300


def test_empty_setlist_is_within_any_limit():
    assert check_running_time([], 1) == []


def test_running_time_exactly_at_limit_is_fine():
    items = [song_item(1, "Bad", duration=300), song_item(2, "Thriller", duration=300)]
    assert check_running_time(items, 10) == []


def test_running_time_over_limit_is_reported():
    items = [song_item(1, "Bad", duration=300), song_item(2, "Thriller", duration=330)]
    problems = check_running_time(items, 10)
    assert problems == ["Running time is 10:30, 0:30 over the 10-minute limit."]


def test_breaks_count_towards_running_time():
    items = [song_item(1, "Bad", duration=540), break_item(2, 120)]
    assert len(check_running_time(items, 10)) == 1


# Outfit changes ---------------------------------------------------------


def test_same_outfit_needs_no_break():
    items = [
        song_item(1, "Bad", outfit_id=1, change_seconds=90),
        song_item(2, "Smooth Criminal", outfit_id=1, change_seconds=90),
    ]
    assert check_outfit_changes(items) == []


def test_outfit_change_without_break_is_reported():
    items = [
        song_item(1, "Bad", outfit_id=1),
        song_item(2, "Thriller", outfit_id=2, change_seconds=90),
    ]
    problems = check_outfit_changes(items)
    assert len(problems) == 1
    assert "Position 2" in problems[0]
    assert "Thriller" in problems[0]


def test_outfit_change_with_long_enough_break_is_fine():
    items = [
        song_item(1, "Bad", outfit_id=1),
        break_item(2, 90),
        song_item(3, "Thriller", outfit_id=2, change_seconds=90),
    ]
    assert check_outfit_changes(items) == []


def test_outfit_change_with_short_break_is_reported():
    items = [
        song_item(1, "Bad", outfit_id=1),
        break_item(2, 60),
        song_item(3, "Thriller", outfit_id=2, change_seconds=90),
    ]
    assert len(check_outfit_changes(items)) == 1


def test_breaks_in_a_row_add_up():
    items = [
        song_item(1, "Bad", outfit_id=1),
        break_item(2, 45),
        break_item(3, 45),
        song_item(4, "Thriller", outfit_id=2, change_seconds=90),
    ]
    assert check_outfit_changes(items) == []


def test_break_only_counts_before_the_next_song():
    # The long break comes before "Bad", so the change after it is not covered.
    items = [
        break_item(1, 300),
        song_item(2, "Bad", outfit_id=1),
        song_item(3, "Thriller", outfit_id=2, change_seconds=90),
    ]
    assert len(check_outfit_changes(items)) == 1


def test_first_song_needs_no_change_time():
    items = [song_item(1, "Thriller", outfit_id=2, change_seconds=90)]
    assert check_outfit_changes(items) == []


def test_missing_song_is_skipped_in_outfit_check():
    items = [
        song_item(1, "Bad", outfit_id=1),
        missing_song_item(2),
        song_item(3, "Smooth Criminal", outfit_id=1),
    ]
    assert check_outfit_changes(items) == []
