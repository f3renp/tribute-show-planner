"""Tests for the catalogue's JSON API (catalogue/api.py), the JSON errors and
CORS (cors.py), through Flask's test client.

create_app() seeds the demo catalogue into catalogue_test, so the demo
songs and outfits are there to ask for.
"""
import pytest

import config
import main
from catalogue import repository

pytestmark = pytest.mark.usefixtures("database")

UI_ORIGIN = "http://localhost:8080"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "CORS_ORIGINS", [UI_ORIGIN])
    return main.create_app().test_client()


def song_id(title, album):
    return repository.find_song_by_title_and_album(title, album)["id"]


def outfit_id(name):
    return repository.find_outfit_by_name(name)["id"]


def new_song_body(**changes):
    """A valid POST /api/songs body, with numbers as JSON numbers."""
    body = {
        "title": "Dirty Diana",
        "album": "Bad",
        "year": 1987,
        "duration": "4:52",
        "energy": 4,
        "kind": "dance",
        "outfit_id": outfit_id("Buckle outfit"),
    }
    body.update(changes)
    return body


def test_health_says_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


# Seam endpoints used by the shows service (unchanged) -------------------


def test_songs_by_ids_returns_the_details_the_show_builder_needs(client):
    billie_jean = song_id("Billie Jean", "Thriller")
    response = client.get(f"/api/songs?ids={billie_jean}")
    assert response.status_code == 200
    [song] = response.get_json()
    assert song["id"] == billie_jean
    assert song["duration_seconds"] == 294
    assert song["outfit_name"] == "Sequin jacket"
    assert song["outfit_change_seconds"] == 120


def test_songs_by_ids_leaves_out_unknown_ids(client):
    billie_jean = song_id("Billie Jean", "Thriller")
    response = client.get(f"/api/songs?ids={billie_jean},9999")
    assert [song["id"] for song in response.get_json()] == [billie_jean]


def test_songs_by_ids_with_no_ids_is_empty(client):
    assert client.get("/api/songs").get_json() == []


def test_songs_by_ids_rejects_ids_that_are_not_numbers(client):
    response = client.get("/api/songs?ids=1,two")
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": ["ids must be whole numbers separated by commas."]
    }


def test_active_songs_leave_out_retired_ones(client):
    titles = [song["title"] for song in client.get("/api/songs/active").get_json()]
    assert "Billie Jean" in titles
    assert "Ben" not in titles


# Reading songs ----------------------------------------------------------


def test_all_songs_include_retired_ones_after_the_active_ones(client):
    songs = client.get("/api/songs/all").get_json()
    assert len(songs) == 20
    assert songs[-1]["title"] == "Ben"
    assert songs[-1]["active"] == 0


def test_songs_come_with_their_duration_as_text(client):
    songs = client.get("/api/songs/all").get_json()
    billie_jean = next(song for song in songs if song["title"] == "Billie Jean")
    assert billie_jean["duration"] == "4:54"
    assert billie_jean["outfit_name"] == "Sequin jacket"


def test_get_one_song(client):
    billie_jean = song_id("Billie Jean", "Thriller")
    response = client.get(f"/api/songs/{billie_jean}")
    assert response.status_code == 200
    assert response.get_json()["title"] == "Billie Jean"
    assert response.get_json()["duration"] == "4:54"


def test_get_an_unknown_song_is_404(client):
    response = client.get("/api/songs/9999")
    assert response.status_code == 404
    assert response.get_json() == {"errors": ["Song 9999 does not exist."]}


def test_a_song_path_that_is_not_a_number_is_404(client):
    # <int:song_id> only matches digits, so this is no route at all.
    response = client.get("/api/songs/abc")
    assert response.status_code == 404
    assert "errors" in response.get_json()


# Adding songs -----------------------------------------------------------


def test_create_song_returns_201_and_the_saved_song(client):
    response = client.post("/api/songs", json=new_song_body())
    assert response.status_code == 201
    song = response.get_json()
    assert song["title"] == "Dirty Diana"
    assert song["duration_seconds"] == 292
    assert song["active"] == 1
    assert repository.get_song(song["id"])["title"] == "Dirty Diana"


def test_create_song_accepts_numbers_sent_as_text(client):
    body = new_song_body(year="1987", energy="4")
    assert client.post("/api/songs", json=body).status_code == 201


def test_create_song_with_no_fields_lists_every_error_at_once(client):
    response = client.post("/api/songs", json={})
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": [
            "Title is required.",
            "Album is required.",
            "Year must be between 1964 and 2014.",
            "Duration must look like 4:54.",
            "Energy must be between 1 and 5.",
            "Kind must be dance or ballad.",
            "Choose an outfit.",
        ]
    }


def test_create_song_with_errors_saves_nothing(client):
    client.post("/api/songs", json=new_song_body(energy=9))
    assert repository.find_song_by_title_and_album("Dirty Diana", "Bad") is None


def test_create_song_with_null_values_reports_them(client):
    response = client.post("/api/songs", json=new_song_body(title=None))
    assert response.status_code == 400
    assert response.get_json() == {"errors": ["Title is required."]}


def test_create_song_with_an_unknown_outfit_is_400(client):
    response = client.post("/api/songs", json=new_song_body(outfit_id=9999))
    assert response.status_code == 400
    assert response.get_json() == {"errors": ["That outfit does not exist."]}


def test_create_song_twice_is_400(client):
    client.post("/api/songs", json=new_song_body())
    response = client.post("/api/songs", json=new_song_body())
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": ["This title and album is already in the catalogue."]
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": "title=Dirty Diana", "content_type": "application/x-www-form-urlencoded"},
        {"data": "not json", "content_type": "application/json"},
        {"json": ["a", "list"]},
    ],
)
def test_create_song_needs_a_json_object(client, kwargs):
    response = client.post("/api/songs", **kwargs)
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": ["The request body must be a JSON object."]
    }


# Editing, retiring and reactivating songs -------------------------------


def test_update_song_saves_the_changes(client):
    billie_jean = song_id("Billie Jean", "Thriller")
    song = client.get(f"/api/songs/{billie_jean}").get_json()
    song["duration"] = "5:10"
    response = client.put(f"/api/songs/{billie_jean}", json=song)
    assert response.status_code == 200
    assert response.get_json()["duration_seconds"] == 310


def test_a_song_read_from_the_api_can_be_sent_back_unchanged(client):
    # The edit form fills itself from GET and sends it back with PUT: the
    # duration text and the numbers must pass the validation as they are.
    billie_jean = song_id("Billie Jean", "Thriller")
    song = client.get(f"/api/songs/{billie_jean}").get_json()
    assert client.put(f"/api/songs/{billie_jean}", json=song).get_json() == song


def test_update_song_with_errors_is_400_and_saves_nothing(client):
    billie_jean = song_id("Billie Jean", "Thriller")
    response = client.put(
        f"/api/songs/{billie_jean}", json=new_song_body(duration="0:10")
    )
    assert response.status_code == 400
    assert response.get_json() == {"errors": ["Duration must be between 0:30 and 20:00."]}
    assert repository.get_song(billie_jean)["title"] == "Billie Jean"


def test_update_an_unknown_song_is_404(client):
    response = client.put("/api/songs/9999", json=new_song_body())
    assert response.status_code == 404


def test_retire_and_reactivate_a_song(client):
    billie_jean = song_id("Billie Jean", "Thriller")
    retired = client.post(f"/api/songs/{billie_jean}/retire")
    assert retired.status_code == 200
    assert retired.get_json()["active"] == 0
    reactivated = client.post(f"/api/songs/{billie_jean}/reactivate")
    assert reactivated.status_code == 200
    assert reactivated.get_json()["active"] == 1


@pytest.mark.parametrize("action", ["retire", "reactivate"])
def test_retire_or_reactivate_an_unknown_song_is_404(client, action):
    assert client.post(f"/api/songs/9999/{action}").status_code == 404


def test_wrong_method_is_405_with_a_json_error(client):
    response = client.delete("/api/songs/1")
    assert response.status_code == 405
    assert "errors" in response.get_json()
    assert "PUT" in response.headers["Allow"]


# Outfits ----------------------------------------------------------------


def test_list_outfits_with_how_many_songs_use_each(client):
    outfits = client.get("/api/outfits").get_json()
    assert len(outfits) == 7
    tuxedo = next(outfit for outfit in outfits if outfit["name"] == "Tuxedo")
    assert tuxedo["change_seconds"] == 90
    assert tuxedo["song_count"] == 3


def test_create_outfit_returns_201_and_the_outfit(client):
    response = client.post("/api/outfits", json={"name": "Gold armour", "change_seconds": 200})
    assert response.status_code == 201
    outfit = response.get_json()
    assert outfit["name"] == "Gold armour"
    assert outfit["change_seconds"] == 200
    assert outfit["song_count"] == 0


def test_create_outfit_with_no_fields_lists_every_error_at_once(client):
    response = client.post("/api/outfits", json={})
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": [
            "Name is required.",
            "Change time must be between 0 and 600 seconds.",
        ]
    }


def test_create_outfit_with_a_taken_name_is_400(client):
    response = client.post("/api/outfits", json={"name": "Tuxedo", "change_seconds": 60})
    assert response.status_code == 400
    assert response.get_json() == {"errors": ["An outfit with this name already exists."]}


def test_update_outfit_saves_the_changes(client):
    tuxedo = outfit_id("Tuxedo")
    response = client.put(
        f"/api/outfits/{tuxedo}", json={"name": "White tuxedo", "change_seconds": 100}
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "id": tuxedo,
        "name": "White tuxedo",
        "change_seconds": 100,
        "song_count": 3,
    }


def test_update_outfit_with_another_outfits_name_is_400_and_saves_nothing(client):
    tuxedo = outfit_id("Tuxedo")
    response = client.put(
        f"/api/outfits/{tuxedo}", json={"name": "Sequin jacket", "change_seconds": 90}
    )
    assert response.status_code == 400
    assert repository.get_outfit(tuxedo)["name"] == "Tuxedo"


def test_update_an_unknown_outfit_is_404(client):
    response = client.put("/api/outfits/9999", json={"name": "X", "change_seconds": 0})
    assert response.status_code == 404
    assert response.get_json() == {"errors": ["Outfit 9999 does not exist."]}


def test_delete_an_unused_outfit_is_204(client):
    created = client.post("/api/outfits", json={"name": "Gold armour", "change_seconds": 200})
    new_id = created.get_json()["id"]
    response = client.delete(f"/api/outfits/{new_id}")
    assert response.status_code == 204
    assert response.data == b""
    assert repository.get_outfit(new_id) is None


def test_delete_an_outfit_songs_use_is_409_and_deletes_nothing(client):
    tuxedo = outfit_id("Tuxedo")
    response = client.delete(f"/api/outfits/{tuxedo}")
    assert response.status_code == 409
    assert response.get_json() == {
        "errors": [
            "This outfit is used by 3 songs (retired ones count too). "
            "Move them to another outfit first."
        ]
    }
    assert repository.get_outfit(tuxedo) is not None


def test_delete_an_unknown_outfit_is_404(client):
    assert client.delete("/api/outfits/9999").status_code == 404


# Errors that are not raised on purpose ----------------------------------


def test_an_unexpected_error_is_a_generic_json_500(client, monkeypatch):
    def broken():
        raise RuntimeError("secret detail")

    monkeypatch.setattr(repository, "list_outfits_with_song_count", broken)
    response = client.get("/api/outfits")
    assert response.status_code == 500
    [message] = response.get_json()["errors"]
    assert "secret detail" not in message


# CORS -------------------------------------------------------------------


def test_the_ui_origin_may_read_the_answer(client):
    response = client.get("/api/outfits", headers={"Origin": UI_ORIGIN})
    assert response.headers["Access-Control-Allow-Origin"] == UI_ORIGIN
    assert "Origin" in response.headers["Vary"]


def test_another_origin_gets_no_cors_headers(client):
    response = client.get("/api/outfits", headers={"Origin": "http://evil.example"})
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers
    assert "Origin" in response.headers["Vary"]


def test_preflight_from_the_ui_allows_json_puts(client):
    response = client.options(
        "/api/songs/1",
        headers={
            "Origin": UI_ORIGIN,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == UI_ORIGIN
    assert "PUT" in response.headers["Access-Control-Allow-Methods"]
    assert response.headers["Access-Control-Allow-Headers"] == "Content-Type"
    assert response.headers["Access-Control-Max-Age"] == "600"


def test_preflight_from_another_origin_gets_no_cors_headers(client):
    response = client.options(
        "/api/songs/1",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "PUT"},
    )
    assert "Access-Control-Allow-Origin" not in response.headers
    assert "Access-Control-Allow-Methods" not in response.headers


def test_errors_carry_cors_headers_too(client):
    # Otherwise the browser would hide the 400 messages from the UI.
    response = client.post("/api/songs", json={}, headers={"Origin": UI_ORIGIN})
    assert response.status_code == 400
    assert response.headers["Access-Control-Allow-Origin"] == UI_ORIGIN


def test_no_origins_configured_allows_none(client, monkeypatch):
    monkeypatch.setattr(config, "CORS_ORIGINS", [])
    response = client.get("/api/outfits", headers={"Origin": UI_ORIGIN})
    assert "Access-Control-Allow-Origin" not in response.headers
