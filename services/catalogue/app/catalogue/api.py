"""The catalogue's JSON API, used by the static UI (ui/) and by the shows
service. Each route reads the request, calls the service or repository,
and returns JSON. No rules live here (ADR-4).

Errors always look like {"errors": ["message", ...]}:
- 400: the body is not a JSON object, or the values do not validate
  (every field error at once, as validate_song/validate_outfit list them);
- 404: no song or outfit with that id;
- 409: the outfit cannot be removed because songs use it.

<int:...> in the paths only matches digits, so /api/songs/all and
/api/songs/active can never be read as a song id.
"""
from flask import Blueprint, abort, request

from catalogue import repository, service

bp = Blueprint("catalogue_api", __name__, url_prefix="/api")


def read_form():
    """The JSON body as a dict of strings, ready for the validate_* functions.

    The validation was written for HTML forms, where every value is text.
    Turning each value into text means 1982 and "1982" are checked the same
    way. A missing field stays missing and is reported by the validation;
    null becomes "" (empty), which is reported the same way.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, "The request body must be a JSON object.")
    return {key: "" if value is None else str(value) for key, value in body.items()}


def errors_response(errors, status):
    """The JSON body and status code for a list of error messages."""
    return {"errors": errors}, status


# Songs ------------------------------------------------------------------


def song_json(song):
    """A song as the API sends it: the database row plus duration as "4:54",
    so the UI shows and sends back the same text the service parses."""
    return dict(song, duration=service.format_duration(song["duration_seconds"]))


def find_song_or_404(song_id):
    """The song with this id and its outfit details, or stop with a 404."""
    songs = service.get_songs_by_ids([song_id])
    if song_id not in songs:
        abort(404, f"Song {song_id} does not exist.")
    return songs[song_id]


@bp.route("/songs")
def songs_by_ids():
    """GET /api/songs?ids=3,7,12 -> the songs with these ids, as a list.

    Used by the shows service. Ids that do not exist are simply missing
    from the list. No ids gives an empty list.
    """
    text = request.args.get("ids", "").strip()
    try:
        song_ids = [int(part) for part in text.split(",")] if text else []
    except ValueError:
        abort(400, "ids must be whole numbers separated by commas.")
    return list(service.get_songs_by_ids(song_ids).values())


@bp.route("/songs/active")
def active_songs():
    """GET /api/songs/active -> the songs that can be added to a setlist.
    Used by the shows service."""
    return service.list_active_songs()


@bp.route("/songs/all")
def all_songs():
    """GET /api/songs/all -> every song, active first, then by title."""
    return [song_json(song) for song in repository.list_songs()]


@bp.route("/songs/<int:song_id>")
def get_song(song_id):
    """GET /api/songs/7 -> one song, to fill the edit form."""
    return song_json(find_song_or_404(song_id))


@bp.route("/songs", methods=["POST"])
def create_song():
    """POST /api/songs -> 201 and the new song, or 400 and the errors."""
    song_id, errors = service.add_song(read_form())
    if errors:
        return errors_response(errors, 400)
    return song_json(find_song_or_404(song_id)), 201


@bp.route("/songs/<int:song_id>", methods=["PUT"])
def update_song(song_id):
    """PUT /api/songs/7 -> the saved song, 400 and the errors, or 404.

    PUT replaces the whole song, so the body has every field, as in POST.
    """
    find_song_or_404(song_id)
    errors = service.edit_song(song_id, read_form())
    if errors:
        return errors_response(errors, 400)
    return song_json(find_song_or_404(song_id))


@bp.route("/songs/<int:song_id>/retire", methods=["POST"])
def retire_song(song_id):
    """POST /api/songs/7/retire -> the song, now with active 0."""
    find_song_or_404(song_id)
    service.retire_song(song_id)
    return song_json(find_song_or_404(song_id))


@bp.route("/songs/<int:song_id>/reactivate", methods=["POST"])
def reactivate_song(song_id):
    """POST /api/songs/7/reactivate -> the song, now with active 1."""
    find_song_or_404(song_id)
    service.reactivate_song(song_id)
    return song_json(find_song_or_404(song_id))


# Outfits ----------------------------------------------------------------


def find_outfit_or_404(outfit_id):
    """The outfit with this id and its song_count, or stop with a 404.

    Same fields as each item of GET /api/outfits.
    """
    outfit = repository.get_outfit(outfit_id)
    if outfit is None:
        abort(404, f"Outfit {outfit_id} does not exist.")
    return dict(outfit, song_count=repository.count_songs_using_outfit(outfit_id))


@bp.route("/outfits")
def list_outfits():
    """GET /api/outfits -> every outfit by name, with its song_count."""
    return repository.list_outfits_with_song_count()


@bp.route("/outfits", methods=["POST"])
def create_outfit():
    """POST /api/outfits -> 201 and the new outfit, or 400 and the errors."""
    outfit_id, errors = service.add_outfit(read_form())
    if errors:
        return errors_response(errors, 400)
    return find_outfit_or_404(outfit_id), 201


@bp.route("/outfits/<int:outfit_id>", methods=["PUT"])
def update_outfit(outfit_id):
    """PUT /api/outfits/3 -> the saved outfit, 400 and the errors, or 404."""
    find_outfit_or_404(outfit_id)
    errors = service.edit_outfit(outfit_id, read_form())
    if errors:
        return errors_response(errors, 400)
    return find_outfit_or_404(outfit_id)


@bp.route("/outfits/<int:outfit_id>", methods=["DELETE"])
def delete_outfit(outfit_id):
    """DELETE /api/outfits/3 -> 204 (no body), 404, or 409 if songs use it."""
    find_outfit_or_404(outfit_id)
    errors = service.remove_outfit(outfit_id)
    if errors:
        return errors_response(errors, 409)
    return "", 204
