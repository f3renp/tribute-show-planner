"""Catalogue rules: duration parsing and validation of songs and outfits.

These functions take plain values and return plain values. They do not
touch the database or Flask, so they can be unit tested on their own.
"""

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

    form is a dict of strings, as it arrives from an HTML form. song holds
    the cleaned, typed values. It may only be saved if errors is empty.
    The duplicate title and album check needs the database, so it is not
    done here.
    """
    errors = []

    title = form.get("title", "").strip()
    if not title:
        errors.append("Title is required.")

    album = form.get("album", "").strip()
    if not album:
        errors.append("Album is required.")

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

    change_seconds = parse_whole_number(form.get("change_seconds", ""))
    if change_seconds is None or not 0 <= change_seconds <= MAX_CHANGE_SECONDS:
        errors.append(
            f"Change time must be between 0 and {MAX_CHANGE_SECONDS} seconds."
        )

    outfit = {"name": name, "change_seconds": change_seconds}
    return outfit, errors
