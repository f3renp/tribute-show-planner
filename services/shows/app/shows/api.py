"""The show builder's JSON API, used by the static UI (ui/). Each route reads
the request, calls the service or repository, and returns JSON. No rules
live here (ADR-4).

Errors always look like {"errors": ["message", ...]}:
- 400: the body is not a JSON object, or the values do not validate
  (every field error at once);
- 404: no show with that id, or no item with that id in that show;
- 503: a song cannot be added because the catalogue is unavailable.

Every change to a setlist answers with the show's new overview, so the UI
redraws the page from one answer and the checks are always up to date.
"""
from flask import Blueprint, abort, request

from shows import repository, service
from shows.rules import format_duration

bp = Blueprint("shows_api", __name__, url_prefix="/api")


def read_form():
    """The JSON body as a dict of strings, ready for the validate_* functions.

    The validation was written for HTML forms, where every value is text.
    Turning each value into text means 90 and "90" are checked the same way.
    A missing field stays missing and is reported by the validation; null
    becomes "" (empty), which is reported the same way.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, "The request body must be a JSON object.")
    return {key: "" if value is None else str(value) for key, value in body.items()}


def errors_response(errors, status):
    """The JSON body and status code for a list of error messages."""
    return {"errors": errors}, status


# Turning rows into JSON -------------------------------------------------


def show_json(show):
    """A show as the API sends it. pymssql gives show_date as a Python date,
    which Flask would send as "Sat, 31 Oct 2026 00:00:00 GMT"; isoformat()
    sends "2026-10-31", the same text the form sends back."""
    return dict(show, show_date=show["show_date"].isoformat())


def song_json(song):
    """A song from the catalogue plus duration as "4:54", for the UI."""
    return dict(song, duration=format_duration(song["duration_seconds"]))


def item_json(item):
    """A setlist item; a song item's "song" is its details, or None."""
    song = item["song"]
    return dict(item, song=None if song is None else song_json(song))


def overview_json(show):
    """The show page as JSON: the show, its setlist and the check results.

    When the catalogue is unavailable, catalogue_available is false and
    total_seconds, total_duration, over_limit and problems are null: the
    checks were skipped (an empty problems list would mean "no problems").
    """
    overview = service.show_overview(show)
    total_seconds = overview["total_seconds"]
    return {
        "show": show_json(show),
        "catalogue_available": overview["catalogue_available"],
        "items": [item_json(item) for item in overview["items"]],
        "total_seconds": total_seconds,
        "total_duration": None if total_seconds is None else format_duration(total_seconds),
        "over_limit": overview["over_limit"],
        "problems": overview["problems"],
        "songs": [song_json(song) for song in overview["songs"]],
    }


def find_show_or_404(show_id):
    """The show with this id, or stop with a 404."""
    show = repository.get_show(show_id)
    if show is None:
        abort(404, f"Show {show_id} does not exist.")
    return show


def check_item_or_404(show_id, item_id):
    """Stop with a 404 unless item_id is in this show's setlist."""
    if not service.is_item_in_show(show_id, item_id):
        abort(404, f"Show {show_id} has no item {item_id}.")


# Shows ------------------------------------------------------------------


@bp.route("/shows")
def list_shows():
    """GET /api/shows -> every show, the soonest first."""
    return [show_json(show) for show in repository.list_shows()]


@bp.route("/shows", methods=["POST"])
def create_show():
    """POST /api/shows -> 201 and the new show, or 400 and the errors."""
    show_id, errors = service.create_show(read_form())
    if errors:
        return errors_response(errors, 400)
    return show_json(find_show_or_404(show_id)), 201


@bp.route("/shows/<int:show_id>")
def get_show(show_id):
    """GET /api/shows/4 -> the show's overview, even if the catalogue is down."""
    return overview_json(find_show_or_404(show_id))


@bp.route("/shows/<int:show_id>", methods=["PUT"])
def update_show(show_id):
    """PUT /api/shows/4 -> the new overview, 400 and the errors, or 404.

    The overview, not just the show: a new length changes the running
    time check, and the UI edits the show from its own page.
    """
    find_show_or_404(show_id)
    errors = service.edit_show(show_id, read_form())
    if errors:
        return errors_response(errors, 400)
    return overview_json(find_show_or_404(show_id))


@bp.route("/shows/<int:show_id>", methods=["DELETE"])
def delete_show(show_id):
    """DELETE /api/shows/4 -> 204 (no body) or 404. Its setlist goes too."""
    find_show_or_404(show_id)
    service.delete_show(show_id)
    return "", 204


# Setlist items ----------------------------------------------------------


@bp.route("/shows/<int:show_id>/songs", methods=["POST"])
def add_song(show_id):
    """POST /api/shows/4/songs {song_id} -> 201 and the new overview.

    400 if the song is missing, unknown or retired; 503 if the catalogue
    is unavailable, since the song cannot be checked (nothing is saved).
    """
    show = find_show_or_404(show_id)
    song_id = service.parse_whole_number(read_form().get("song_id", ""))
    errors = service.add_song_to_setlist(show_id, song_id)
    if errors == [service.CATALOGUE_DOWN_ADD_SONG]:
        return errors_response(errors, 503)
    if errors:
        return errors_response(errors, 400)
    return overview_json(show), 201


@bp.route("/shows/<int:show_id>/breaks", methods=["POST"])
def add_break(show_id):
    """POST /api/shows/4/breaks {break_label, break_seconds} -> 201 and the
    new overview, or 400 and the errors."""
    show = find_show_or_404(show_id)
    errors = service.add_break_to_setlist(show_id, read_form())
    if errors:
        return errors_response(errors, 400)
    return overview_json(show), 201


@bp.route("/shows/<int:show_id>/items/<int:item_id>/move", methods=["POST"])
def move_item(show_id, item_id):
    """POST /api/shows/4/items/9/move {direction: "up" or "down"} -> the new
    overview. The first item moving up (or last moving down) stays put."""
    show = find_show_or_404(show_id)
    check_item_or_404(show_id, item_id)
    direction = read_form().get("direction", "").strip()
    if direction not in service.DIRECTIONS:
        return errors_response(["Direction must be up or down."], 400)
    service.move_item(show_id, item_id, direction)
    return overview_json(show)


@bp.route("/shows/<int:show_id>/items/<int:item_id>", methods=["DELETE"])
def remove_item(show_id, item_id):
    """DELETE /api/shows/4/items/9 -> the new overview, or 404."""
    show = find_show_or_404(show_id)
    check_item_or_404(show_id, item_id)
    service.remove_item(show_id, item_id)
    return overview_json(show)
