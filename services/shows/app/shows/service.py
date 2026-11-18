"""Show builder rules: validating shows and breaks, and editing setlists.

validate_show, validate_break and move_in_order take plain values and
return plain values, with no database or Flask, so they can be unit
tested on their own. The functions below them save through the
repository. Song details only ever come from the catalogue service, over
HTTP through shows.catalogue_client.
"""
from datetime import date

from shows import catalogue_client, repository, rules
from shows.catalogue_client import CatalogueUnavailable
from shows.rules import format_duration

# A show longer than 4 hours is a typo.
MAX_SHOW_MINUTES = 4 * 60

# A break longer than 30 minutes is an interval, not a break in the set.
MAX_BREAK_SECONDS = 30 * 60

# Sizes of the NVARCHAR columns in migrations/001_init.sql. Longer text
# would be refused by SQL Server, so the form reports it first.
MAX_NAME_LENGTH = 200
MAX_VENUE_LENGTH = 200
MAX_BREAK_LABEL_LENGTH = 100

DIRECTIONS = ("up", "down")

# A song cannot be checked (exists? retired?) without the catalogue, so it
# is not added rather than added unchecked.
CATALOGUE_DOWN_ADD_SONG = (
    "Catalogue service unavailable: the song could not be checked and was "
    "not added. Try again later."
)


def parse_whole_number(text):
    """Turn "90" into 90. Return None if the text is not a whole number."""
    try:
        return int(text.strip())
    except ValueError:
        return None


def validate_show(form):
    """Check a submitted show form and return (show, errors).

    form is a dict of strings (api.py turns the JSON values into text, so
    90 and "90" are checked the same way). show_date must be YYYY-MM-DD,
    which is what <input type="date"> gives.
    """
    errors = []

    name = form.get("name", "").strip()
    if not name:
        errors.append("Name is required.")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"Name must be at most {MAX_NAME_LENGTH} characters.")

    venue = form.get("venue", "").strip()
    if not venue:
        errors.append("Venue is required.")
    elif len(venue) > MAX_VENUE_LENGTH:
        errors.append(f"Venue must be at most {MAX_VENUE_LENGTH} characters.")

    show_date = form.get("show_date", "").strip()
    try:
        date.fromisoformat(show_date)
    except ValueError:
        errors.append("Date must look like 2026-10-31.")

    max_minutes = parse_whole_number(form.get("max_minutes", ""))
    if max_minutes is None or not 1 <= max_minutes <= MAX_SHOW_MINUTES:
        errors.append(f"Length must be between 1 and {MAX_SHOW_MINUTES} minutes.")

    show = {
        "name": name,
        "venue": venue,
        "show_date": show_date,
        "max_minutes": max_minutes,
    }
    return show, errors


def validate_break(form):
    """Check a submitted break form and return (label, seconds, errors)."""
    errors = []

    label = form.get("break_label", "").strip()
    if not label:
        errors.append("Break label is required.")
    elif len(label) > MAX_BREAK_LABEL_LENGTH:
        errors.append(f"Break label must be at most {MAX_BREAK_LABEL_LENGTH} characters.")

    seconds = parse_whole_number(form.get("break_seconds", ""))
    if seconds is None or not 1 <= seconds <= MAX_BREAK_SECONDS:
        errors.append(f"Break must be between 1 and {MAX_BREAK_SECONDS} seconds.")

    return label, seconds, errors


def move_in_order(item_ids, item_id, direction):
    """Return a new list with item_id moved one place "up" or "down".

    The first item cannot move up and the last cannot move down: the
    order comes back unchanged. So does an item_id that is not in the list.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"Direction must be one of {DIRECTIONS}.")
    new_order = list(item_ids)
    if item_id not in new_order:
        return new_order
    index = new_order.index(item_id)
    other = index - 1 if direction == "up" else index + 1
    if 0 <= other < len(new_order):
        new_order[index], new_order[other] = new_order[other], new_order[index]
    return new_order


# Reading: setlists joined with song details from the catalogue ----------


def song_ids_in(items):
    """The song ids of the song items, in setlist order."""
    return [item["song_id"] for item in items if item["item_type"] == "song"]


def attach_songs(items, songs_by_id):
    """Give each item a "song" key: its details, or None if not known."""
    for item in items:
        item["song"] = songs_by_id.get(item["song_id"])
    return items


def get_setlist(show_id):
    """The show's items in order. Each song item gets a "song" key with the
    catalogue's details for it, fetched in one HTTP call through the seam.

    Raises CatalogueUnavailable if the catalogue cannot be reached.
    """
    items = repository.list_items(show_id)
    songs_by_id = catalogue_client.get_songs_by_ids(song_ids_in(items))
    return attach_songs(items, songs_by_id)


def show_overview(show):
    """Everything the show page needs, as plain values.

    When the catalogue is unavailable the show still loads, degraded: the
    setlist (positions, breaks, song ids) comes from our own database, but
    song details are None, the running time is unknown, the checks are
    skipped (problems is None, not an empty list, which would mean "no
    problems"; over_limit is None, not False, which would mean "within the
    limit") and there are no songs to choose from.
    """
    items = repository.list_items(show["id"])
    try:
        songs_by_id = catalogue_client.get_songs_by_ids(song_ids_in(items))
        songs_to_choose = catalogue_client.list_active_songs()
    except CatalogueUnavailable:
        return {
            "catalogue_available": False,
            "items": attach_songs(items, {}),
            "total_seconds": None,
            "over_limit": None,
            "problems": None,
            "songs": [],
        }
    attach_songs(items, songs_by_id)
    total_seconds = rules.setlist_seconds(items)
    return {
        "catalogue_available": True,
        "items": items,
        "total_seconds": total_seconds,
        "over_limit": rules.is_over_limit(total_seconds, show["max_minutes"]),
        "problems": rules.check_setlist(items, show["max_minutes"]),
        "songs": songs_to_choose,
    }


# Saving: these use the database through the repository ------------------


def create_show(form):
    """Validate a show form and save it. Return (show_id, errors).

    show_id is None when there are errors.
    """
    show, errors = validate_show(form)
    if errors:
        return None, errors
    return repository.insert_show(show), []


def edit_show(show_id, form):
    """Validate an edited show form and save it. Return the errors, empty if saved."""
    show, errors = validate_show(form)
    if not errors:
        repository.update_show(show_id, show)
    return errors


def delete_show(show_id):
    """Delete a show and, through ON DELETE CASCADE, its whole setlist."""
    repository.delete_show(show_id)


def is_item_in_show(show_id, item_id):
    """True if item_id is one of this show's setlist items."""
    return any(item["id"] == item_id for item in repository.list_items(show_id))


def add_song_to_setlist(show_id, song_id):
    """Append a song to the end of a show's setlist. Return the errors."""
    if song_id is None:
        return ["Choose a song."]
    try:
        song = catalogue_client.get_songs_by_ids([song_id]).get(song_id)
    except CatalogueUnavailable:
        return [CATALOGUE_DOWN_ADD_SONG]
    if song is None:
        return ["That song is not in the catalogue."]
    if not song["active"]:
        return ["That song is retired."]
    repository.insert_song_item(show_id, repository.next_position(show_id), song_id)
    return []


def add_break_to_setlist(show_id, form):
    """Validate a break form and append it to the setlist. Return the errors."""
    label, seconds, errors = validate_break(form)
    if not errors:
        position = repository.next_position(show_id)
        repository.insert_break_item(show_id, position, label, seconds)
    return errors


def remove_item(show_id, item_id):
    """Delete an item and close the gap it leaves in the positions."""
    remaining = [
        item["id"] for item in repository.list_items(show_id) if item["id"] != item_id
    ]
    repository.delete_item(show_id, item_id)
    repository.save_order(show_id, remaining)


def move_item(show_id, item_id, direction):
    """Move an item one place up or down in its show's setlist."""
    item_ids = [item["id"] for item in repository.list_items(show_id)]
    repository.save_order(show_id, move_in_order(item_ids, item_id, direction))
