"""Catalogue rules: duration parsing, validation, and saving songs and outfits.

The parsing and validate_* functions take plain values and return plain
values, with no database or Flask, so they can be unit tested on their own.
The functions at the bottom (add_song, edit_song, ...) run those checks,
add the checks that need the database, and save through the repository.
"""
from catalogue import repository

# First Jackson 5 recordings to the last posthumous album (Xscape).
MIN_YEAR = 1964
MAX_YEAR = 2014

# A live song shorter than 30 seconds or longer than 20 minutes is a typo.
MIN_DURATION_SECONDS = 30
MAX_DURATION_SECONDS = 20 * 60

MIN_ENERGY = 1
MAX_ENERGY = 5

SONG_KINDS = ("dance", "ballad")

# A costume change longer than 10 minutes would stop the show.
MAX_CHANGE_SECONDS = 10 * 60

# Sizes of the NVARCHAR columns in migrations/001_init.sql. Longer text
# would be refused by SQL Server, so the form reports it first.
MAX_TITLE_LENGTH = 200
MAX_ALBUM_LENGTH = 200
MAX_OUTFIT_NAME_LENGTH = 100


def parse_duration(text):
    """Turn "4:54" into 294 seconds. Raise ValueError if it is not m:ss."""
    parts = text.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Duration must look like 4:54.")
    minutes_text, seconds_text = parts
    if not minutes_text.isdigit() or not seconds_text.isdigit():
        raise ValueError("Duration must look like 4:54.")
    if len(seconds_text) != 2 or int(seconds_text) > 59:
        raise ValueError("Seconds must be two digits between 00 and 59.")
    return int(minutes_text) * 60 + int(seconds_text)


def format_duration(seconds):
    """Turn 294 seconds into "4:54"."""
    return f"{seconds // 60}:{seconds % 60:02d}"


def parse_whole_number(text):
    """Turn "5" into 5. Return None if the text is not a whole number."""
    try:
        return int(text.strip())
    except ValueError:
        return None


def read_duration(text):
    """Parse a duration and check its range. Return (seconds, error)."""
    try:
        seconds = parse_duration(text)
    except ValueError as error:
        return None, str(error)
    if not MIN_DURATION_SECONDS <= seconds <= MAX_DURATION_SECONDS:
        low = format_duration(MIN_DURATION_SECONDS)
        high = format_duration(MAX_DURATION_SECONDS)
        return None, f"Duration must be between {low} and {high}."
    return seconds, None


def validate_song(form):
    """Check a submitted song form and return (song, errors).

    form is a dict of strings (api.py turns the JSON values into text, so
    a year sent as 1982 or "1982" is checked the same way). song holds
    the cleaned, typed values. It may only be saved if errors is empty.
    The duplicate title and album check needs the database, so it is not
    done here.
    """
    errors = []

    title = form.get("title", "").strip()
    if not title:
        errors.append("Title is required.")
    elif len(title) > MAX_TITLE_LENGTH:
        errors.append(f"Title must be at most {MAX_TITLE_LENGTH} characters.")

    album = form.get("album", "").strip()
    if not album:
        errors.append("Album is required.")
    elif len(album) > MAX_ALBUM_LENGTH:
        errors.append(f"Album must be at most {MAX_ALBUM_LENGTH} characters.")

    year = parse_whole_number(form.get("year", ""))
    if year is None or not MIN_YEAR <= year <= MAX_YEAR:
        errors.append(f"Year must be between {MIN_YEAR} and {MAX_YEAR}.")

    duration_seconds, duration_error = read_duration(form.get("duration", ""))
    if duration_error:
        errors.append(duration_error)

    energy = parse_whole_number(form.get("energy", ""))
    if energy is None or not MIN_ENERGY <= energy <= MAX_ENERGY:
        errors.append(f"Energy must be between {MIN_ENERGY} and {MAX_ENERGY}.")

    kind = form.get("kind", "").strip()
    if kind not in SONG_KINDS:
        errors.append("Kind must be dance or ballad.")

    outfit_id = parse_whole_number(form.get("outfit_id", ""))
    if outfit_id is None:
        errors.append("Choose an outfit.")

    song = {
        "title": title,
        "album": album,
        "year": year,
        "duration_seconds": duration_seconds,
        "energy": energy,
        "kind": kind,
        "outfit_id": outfit_id,
    }
    return song, errors


def validate_outfit(form):
    """Check a submitted outfit form and return (outfit, errors)."""
    errors = []

    name = form.get("name", "").strip()
    if not name:
        errors.append("Name is required.")
    elif len(name) > MAX_OUTFIT_NAME_LENGTH:
        errors.append(f"Name must be at most {MAX_OUTFIT_NAME_LENGTH} characters.")

    change_seconds = parse_whole_number(form.get("change_seconds", ""))
    if change_seconds is None or not 0 <= change_seconds <= MAX_CHANGE_SECONDS:
        errors.append(
            f"Change time must be between 0 and {MAX_CHANGE_SECONDS} seconds."
        )

    outfit = {"name": name, "change_seconds": change_seconds}
    return outfit, errors


# Saving: these use the database through the repository ------------------


def check_song_against_catalogue(song, song_id=None):
    """Checks that need the database: the outfit exists, no duplicate song.

    song_id is the song being edited, so it is not reported as a
    duplicate of itself. It is None when adding a new song.
    """
    errors = []
    if repository.get_outfit(song["outfit_id"]) is None:
        errors.append("That outfit does not exist.")
    existing = repository.find_song_by_title_and_album(song["title"], song["album"])
    if existing is not None and existing["id"] != song_id:
        errors.append("This title and album is already in the catalogue.")
    return errors


def add_song(form):
    """Validate a new song form and save it. Return (new_id, errors).

    new_id is None when nothing was saved; errors is empty when it was.
    """
    song, errors = validate_song(form)
    if not errors:
        errors = check_song_against_catalogue(song)
    if errors:
        return None, errors
    return repository.insert_song(song), []


def edit_song(song_id, form):
    """Validate an edited song form and save it. Return the errors, empty if saved."""
    song, errors = validate_song(form)
    if not errors:
        errors = check_song_against_catalogue(song, song_id)
    if not errors:
        repository.update_song(song_id, song)
    return errors


def get_songs_by_ids(song_ids):
    """Song details for other domains, as a dict {song_id: song}.

    The shows service reaches it over HTTP through GET /api/songs
    (catalogue/api.py). Ids that do not exist are simply missing from the
    result.
    """
    songs = repository.get_songs_with_outfits(song_ids)
    return {song["id"]: song for song in songs}


def list_active_songs():
    """Songs that can be added to a setlist, for the show builder's picker."""
    return [song for song in repository.list_songs() if song["active"]]


def retire_song(song_id):
    """Hide a song from new setlists without deleting it."""
    repository.set_song_active(song_id, False)


def reactivate_song(song_id):
    """Make a retired song available for setlists again."""
    repository.set_song_active(song_id, True)


def check_outfit_name_is_free(name, outfit_id=None):
    """Errors if another outfit already has this name.

    outfit_id is the outfit being edited, so keeping its own name is fine.
    It is None when adding a new outfit.
    """
    existing = repository.find_outfit_by_name(name)
    if existing is not None and existing["id"] != outfit_id:
        return ["An outfit with this name already exists."]
    return []


def add_outfit(form):
    """Validate an outfit form and save it. Return (new_id, errors).

    new_id is None when nothing was saved; errors is empty when it was.
    """
    outfit, errors = validate_outfit(form)
    if not errors:
        errors = check_outfit_name_is_free(outfit["name"])
    if errors:
        return None, errors
    return repository.insert_outfit(outfit), []


def edit_outfit(outfit_id, form):
    """Validate an edited outfit form and save it. Return the errors, empty if saved."""
    outfit, errors = validate_outfit(form)
    if not errors:
        errors = check_outfit_name_is_free(outfit["name"], outfit_id)
    if not errors:
        repository.update_outfit(outfit_id, outfit)
    return errors


def remove_outfit(outfit_id):
    """Delete an outfit that no song uses. Return the errors, empty if deleted.

    Retired songs count too: they keep their outfit_id and could be
    reactivated. The foreign key fk_songs_outfit would also refuse the
    delete; checking first gives a clear message instead of a SQL error.
    (A song added between the check and the delete would still hit the
    foreign key, but with one replica and one user that is not expected.)
    """
    song_count = repository.count_songs_using_outfit(outfit_id)
    if song_count:
        noun = "song" if song_count == 1 else "songs"
        return [
            f"This outfit is used by {song_count} {noun} (retired ones count "
            "too). Move them to another outfit first."
        ]
    repository.delete_outfit(outfit_id)
    return []
