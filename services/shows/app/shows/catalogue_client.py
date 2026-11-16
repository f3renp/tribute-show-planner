"""Calls to the catalogue service over HTTP. This file is now the seam:
the rest of the show builder never talks to the catalogue any other way.

It keeps the two functions shows.service used to import from
catalogue.service, with the same return values, so the service code and
the setlist checks did not have to change (ADR-3, ADR-6).

Every way a call can fail is turned into one exception,
CatalogueUnavailable, so callers only have to handle one thing.
"""
import json
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import config


class CatalogueUnavailable(Exception):
    """The catalogue could not be reached or gave an answer we cannot use."""


def get_json(path):
    """GET CATALOGUE_URL + path and return the decoded JSON body.

    Raises CatalogueUnavailable when:
    - the catalogue cannot be reached (URLError, ConnectionError),
    - it answers with a 4xx or 5xx status (HTTPError, a kind of URLError),
    - it takes longer than CATALOGUE_TIMEOUT seconds (TimeoutError),
    - the connection breaks mid-answer (HTTPException),
    - the body is not JSON (ValueError).
    """
    url = config.CATALOGUE_URL.rstrip("/") + path
    try:
        with urlopen(url, timeout=config.CATALOGUE_TIMEOUT) as response:
            return json.load(response)
    except (URLError, TimeoutError, ConnectionError, HTTPException, ValueError) as error:
        raise CatalogueUnavailable(f"GET {url} failed: {error}") from error


def get_songs_by_ids(song_ids):
    """Song details as a dict {song_id: song}, from GET /api/songs?ids=...

    Ids that do not exist are simply missing from the result. No ids means
    no request at all.
    """
    if not song_ids:
        return {}
    ids = ",".join(str(song_id) for song_id in sorted(set(song_ids)))
    songs = get_json("/api/songs?" + urlencode({"ids": ids}))
    return {song["id"]: song for song in songs}


def list_active_songs():
    """Songs that can be added to a setlist, from GET /api/songs/active."""
    return get_json("/api/songs/active")
