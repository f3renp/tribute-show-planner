"""Tests for the show builder's JSON API (shows/api.py), the JSON errors and
CORS (cors.py), through Flask's test client.

The catalogue fixture from conftest.py is a fake catalogue the tests add
songs to; catalogue_down makes every catalogue call fail, as if the
container were stopped. No test calls the real catalogue.
"""
import pytest

import config
import db
import main
from shows import repository

UI_ORIGIN = "http://localhost:8080"


@pytest.fixture
def client(database, catalogue, monkeypatch):
    """A Flask test client on a fresh shows_test database, with an empty
    fake catalogue, so no test calls the real one (with nothing listening,
    each real call takes ~4 s to fail on Windows)."""
    monkeypatch.setattr(config, "CORS_ORIGINS", [UI_ORIGIN])
    return main.create_app().test_client()


def add_catalogue_song(catalogue, title, energy=4, active=1):
    """Put a song in the fake catalogue, shaped like GET /api/songs returns
    it. Return its id."""
    song_id = len(catalogue) + 1
    catalogue[song_id] = {
        "id": song_id,
        "title": title,
        "album": "Thriller",
        "year": 1982,
        "duration_seconds": 294,
        "energy": energy,
        "kind": "dance",
        "outfit_id": 1,
        "active": active,
        "outfit_name": "Red jacket",
        "outfit_change_seconds": 90,
    }
    return song_id


def show_body(**changes):
    """A valid POST /api/shows body, with max_minutes as a JSON number."""
    body = {
        "name": "Halloween night",
        "venue": "Teatro Real",
        "show_date": "2026-10-31",
        "max_minutes": 90,
    }
    body.update(changes)
    return body


def create_show(client, **changes):
    """Create a show through the API and return its id."""
    response = client.post("/api/shows", json=show_body(**changes))
    assert response.status_code == 201
    return response.get_json()["id"]


def save_show_with_song_7_and_a_break():
    """A show saved straight through the repository, without the catalogue
    (for the tests where it is down). Return the show id."""
    show_id = repository.insert_show(
        {"name": "Halloween night", "venue": "Teatro Real",
         "show_date": "2026-10-31", "max_minutes": 90}
    )
    repository.insert_song_item(show_id, 1, 7)
    repository.insert_break_item(show_id, 2, "Rest", 60)
    return show_id


def item_ids(show_id):
    return [item["id"] for item in repository.list_items(show_id)]


# Listing and creating shows ---------------------------------------------


def test_list_shows_soonest_first_with_iso_dates(client):
    create_show(client, name="Christmas", show_date="2026-12-24")
    create_show(client, name="Halloween", show_date="2026-10-31")
    shows = client.get("/api/shows").get_json()
    assert [show["name"] for show in shows] == ["Halloween", "Christmas"]
    assert shows[0]["show_date"] == "2026-10-31"


def test_create_show_returns_201_and_the_show(client):
    response = client.post("/api/shows", json=show_body(max_minutes="90"))
    assert response.status_code == 201
    show = response.get_json()
    assert show["name"] == "Halloween night"
    assert show["show_date"] == "2026-10-31"
    assert show["max_minutes"] == 90


def test_create_show_with_no_fields_lists_every_error_at_once(client):
    response = client.post("/api/shows", json={})
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": [
            "Name is required.",
            "Venue is required.",
            "Date must look like 2026-10-31.",
            "Length must be between 1 and 240 minutes.",
        ]
    }
    assert repository.list_shows() == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": "name=Halloween", "content_type": "application/x-www-form-urlencoded"},
        {"data": "not json", "content_type": "application/json"},
        {"json": ["a", "list"]},
    ],
)
def test_create_show_needs_a_json_object(client, kwargs):
    response = client.post("/api/shows", **kwargs)
    assert response.status_code == 400
    assert response.get_json() == {"errors": ["The request body must be a JSON object."]}


# The overview -----------------------------------------------------------


def test_overview_has_the_setlist_with_details_and_the_checks(client, catalogue):
    show_id = create_show(client)
    billie_jean = add_catalogue_song(catalogue, "Billie Jean")
    client.post(f"/api/shows/{show_id}/songs", json={"song_id": billie_jean})
    response = client.get(f"/api/shows/{show_id}")
    assert response.status_code == 200
    overview = response.get_json()
    assert overview["show"]["show_date"] == "2026-10-31"
    assert overview["catalogue_available"] is True
    [item] = overview["items"]
    assert item["song"]["title"] == "Billie Jean"
    assert item["song"]["duration"] == "4:54"
    assert overview["total_seconds"] == 294
    assert overview["total_duration"] == "4:54"
    assert overview["over_limit"] is False
    assert overview["problems"] == []
    assert overview["songs"][0]["duration"] == "4:54"


def test_overview_of_an_unknown_show_is_404(client):
    response = client.get("/api/shows/9999")
    assert response.status_code == 404
    assert response.get_json() == {"errors": ["Show 9999 does not exist."]}


@pytest.mark.usefixtures("catalogue_down")
def test_overview_is_degraded_not_broken_when_the_catalogue_is_down(client):
    show_id = save_show_with_song_7_and_a_break()
    response = client.get(f"/api/shows/{show_id}")
    assert response.status_code == 200
    overview = response.get_json()
    assert overview["catalogue_available"] is False
    song_item, break_item = overview["items"]
    assert song_item["song_id"] == 7
    assert song_item["song"] is None
    assert break_item["break_label"] == "Rest"
    assert break_item["break_seconds"] == 60
    assert overview["total_seconds"] is None
    assert overview["total_duration"] is None
    assert overview["over_limit"] is None
    assert overview["problems"] is None
    assert overview["songs"] == []


@pytest.mark.usefixtures("catalogue_down")
def test_shows_list_and_health_work_when_the_catalogue_is_down(client):
    save_show_with_song_7_and_a_break()
    assert client.get("/api/shows").status_code == 200
    assert client.get("/health").status_code == 200


# Editing and deleting shows ---------------------------------------------


def test_update_show_answers_with_the_new_overview(client, catalogue):
    show_id = create_show(client)
    song_id = add_catalogue_song(catalogue, "Billie Jean")
    client.post(f"/api/shows/{show_id}/songs", json={"song_id": song_id})
    response = client.put(f"/api/shows/{show_id}", json=show_body(max_minutes=4))
    assert response.status_code == 200
    overview = response.get_json()
    assert overview["show"]["max_minutes"] == 4
    # 4:54 of music no longer fits: the checks ran again with the new limit.
    assert overview["over_limit"] is True
    assert overview["problems"] == [
        "Running time is 4:54, 0:54 over the 4-minute limit."
    ]


def test_a_show_read_from_the_api_can_be_sent_back_unchanged(client, catalogue):
    show_id = create_show(client)
    show = client.get(f"/api/shows/{show_id}").get_json()["show"]
    response = client.put(f"/api/shows/{show_id}", json=show)
    assert response.get_json()["show"] == show


def test_update_show_with_errors_is_400_and_saves_nothing(client):
    show_id = create_show(client)
    response = client.put(
        f"/api/shows/{show_id}", json=show_body(name="", show_date="31/10/2026")
    )
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": ["Name is required.", "Date must look like 2026-10-31."]
    }
    assert repository.get_show(show_id)["name"] == "Halloween night"


def test_update_an_unknown_show_is_404(client):
    assert client.put("/api/shows/9999", json=show_body()).status_code == 404


def test_delete_show_is_204_and_removes_its_setlist(client):
    show_id = create_show(client)
    client.post(f"/api/shows/{show_id}/breaks", json={"break_label": "Rest", "break_seconds": 60})
    response = client.delete(f"/api/shows/{show_id}")
    assert response.status_code == 204
    assert response.data == b""
    assert repository.get_show(show_id) is None
    assert db.fetch_all("SELECT id FROM setlist_items WHERE show_id = %s", (show_id,)) == []


def test_delete_an_unknown_show_is_404(client):
    assert client.delete("/api/shows/9999").status_code == 404


# Adding songs and breaks ------------------------------------------------


def test_add_song_returns_201_and_the_new_overview(client, catalogue):
    show_id = create_show(client)
    song_id = add_catalogue_song(catalogue, "Billie Jean")
    response = client.post(f"/api/shows/{show_id}/songs", json={"song_id": str(song_id)})
    assert response.status_code == 201
    assert [item["song_id"] for item in response.get_json()["items"]] == [song_id]


@pytest.mark.parametrize(
    "body, message",
    [
        ({}, "Choose a song."),
        ({"song_id": "seven"}, "Choose a song."),
        ({"song_id": 99}, "That song is not in the catalogue."),
        ({"song_id": 1}, "That song is retired."),
    ],
)
def test_add_song_refuses_missing_unknown_and_retired_songs(client, catalogue, body, message):
    add_catalogue_song(catalogue, "Ben", active=0)
    show_id = create_show(client)
    response = client.post(f"/api/shows/{show_id}/songs", json=body)
    assert response.status_code == 400
    assert response.get_json() == {"errors": [message]}
    assert repository.list_items(show_id) == []


def test_add_song_to_an_unknown_show_is_404(client, catalogue):
    song_id = add_catalogue_song(catalogue, "Billie Jean")
    response = client.post("/api/shows/9999/songs", json={"song_id": song_id})
    assert response.status_code == 404


@pytest.mark.usefixtures("catalogue_down")
def test_add_song_is_503_and_saves_nothing_when_the_catalogue_is_down(client):
    show_id = save_show_with_song_7_and_a_break()
    response = client.post(f"/api/shows/{show_id}/songs", json={"song_id": 3})
    assert response.status_code == 503
    [message] = response.get_json()["errors"]
    assert "the song could not be checked and was not added" in message
    assert len(repository.list_items(show_id)) == 2


def test_add_break_returns_201_and_the_new_overview(client):
    show_id = create_show(client)
    response = client.post(
        f"/api/shows/{show_id}/breaks", json={"break_label": "Rest", "break_seconds": 90}
    )
    assert response.status_code == 201
    [item] = response.get_json()["items"]
    assert item["item_type"] == "break"
    assert item["break_seconds"] == 90


def test_add_break_with_no_fields_lists_every_error_at_once(client):
    show_id = create_show(client)
    response = client.post(f"/api/shows/{show_id}/breaks", json={})
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": [
            "Break label is required.",
            "Break must be between 1 and 1800 seconds.",
        ]
    }
    assert repository.list_items(show_id) == []


def test_add_break_to_an_unknown_show_is_404(client):
    response = client.post("/api/shows/9999/breaks", json={"break_label": "Rest", "break_seconds": 60})
    assert response.status_code == 404


# Moving and removing items ----------------------------------------------


def three_breaks(client):
    """A show with breaks A, B, C. Return (show_id, [item ids in order])."""
    show_id = create_show(client)
    for label in ["A", "B", "C"]:
        client.post(f"/api/shows/{show_id}/breaks", json={"break_label": label, "break_seconds": 60})
    return show_id, item_ids(show_id)


def labels(overview):
    return [item["break_label"] for item in overview["items"]]


def test_move_up_answers_with_the_new_order(client):
    show_id, (a, b, c) = three_breaks(client)
    response = client.post(f"/api/shows/{show_id}/items/{c}/move", json={"direction": "up"})
    assert response.status_code == 200
    assert labels(response.get_json()) == ["A", "C", "B"]


def test_first_item_moving_up_stays_first(client):
    show_id, (a, b, c) = three_breaks(client)
    response = client.post(f"/api/shows/{show_id}/items/{a}/move", json={"direction": "up"})
    assert response.status_code == 200
    assert labels(response.get_json()) == ["A", "B", "C"]


@pytest.mark.parametrize("body", [{}, {"direction": "sideways"}])
def test_move_needs_up_or_down(client, body):
    show_id, (a, b, c) = three_breaks(client)
    response = client.post(f"/api/shows/{show_id}/items/{b}/move", json=body)
    assert response.status_code == 400
    assert response.get_json() == {"errors": ["Direction must be up or down."]}


def test_move_an_item_of_another_show_is_404(client):
    show_id, (a, b, c) = three_breaks(client)
    other_show_id = create_show(client)
    response = client.post(f"/api/shows/{other_show_id}/items/{a}/move", json={"direction": "up"})
    assert response.status_code == 404
    assert response.get_json() == {"errors": [f"Show {other_show_id} has no item {a}."]}


def test_move_in_an_unknown_show_is_404(client):
    response = client.post("/api/shows/9999/items/1/move", json={"direction": "up"})
    assert response.status_code == 404


def test_remove_item_answers_with_the_closed_up_setlist(client):
    show_id, (a, b, c) = three_breaks(client)
    response = client.delete(f"/api/shows/{show_id}/items/{b}")
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert [item["break_label"] for item in items] == ["A", "C"]
    assert [item["position"] for item in items] == [1, 2]


def test_remove_an_unknown_item_is_404(client):
    show_id, _ = three_breaks(client)
    assert client.delete(f"/api/shows/{show_id}/items/9999").status_code == 404
    assert len(repository.list_items(show_id)) == 3


@pytest.mark.usefixtures("catalogue_down")
def test_moving_still_works_when_the_catalogue_is_down(client):
    show_id = save_show_with_song_7_and_a_break()
    break_id = item_ids(show_id)[1]
    response = client.post(f"/api/shows/{show_id}/items/{break_id}/move", json={"direction": "up"})
    assert response.status_code == 200
    overview = response.get_json()
    assert overview["catalogue_available"] is False
    assert [item["item_type"] for item in overview["items"]] == ["break", "song"]


# Errors that are not raised on purpose ----------------------------------


def test_wrong_method_is_405_with_a_json_error(client):
    response = client.patch("/api/shows")
    assert response.status_code == 405
    assert "errors" in response.get_json()
    assert "POST" in response.headers["Allow"]


def test_an_unexpected_error_is_a_generic_json_500(client, monkeypatch):
    def broken():
        raise RuntimeError("secret detail")

    monkeypatch.setattr(repository, "list_shows", broken)
    response = client.get("/api/shows")
    assert response.status_code == 500
    [message] = response.get_json()["errors"]
    assert "secret detail" not in message


# CORS -------------------------------------------------------------------


def test_the_ui_origin_may_read_the_answer(client):
    response = client.get("/api/shows", headers={"Origin": UI_ORIGIN})
    assert response.headers["Access-Control-Allow-Origin"] == UI_ORIGIN
    assert "Origin" in response.headers["Vary"]


def test_another_origin_gets_no_cors_headers(client):
    response = client.get("/api/shows", headers={"Origin": "http://evil.example"})
    assert "Access-Control-Allow-Origin" not in response.headers


def test_preflight_from_the_ui_allows_json_deletes(client):
    response = client.options(
        "/api/shows/1/items/2",
        headers={"Origin": UI_ORIGIN, "Access-Control-Request-Method": "DELETE"},
    )
    assert response.status_code == 200
    assert "DELETE" in response.headers["Access-Control-Allow-Methods"]
    assert response.headers["Access-Control-Allow-Headers"] == "Content-Type"


# Origin check: changes from another site's page are refused -----------


def test_a_change_from_another_origin_is_403_and_changes_nothing(client):
    show_id, (a, b, c) = three_breaks(client)
    response = client.delete(
        f"/api/shows/{show_id}/items/{a}", headers={"Origin": "http://evil.example"}
    )
    assert response.status_code == 403
    assert response.get_json() == {
        "errors": ["Origin http://evil.example may not change data here."]
    }
    assert len(repository.list_items(show_id)) == 3


def test_a_show_delete_from_another_origin_is_403(client):
    show_id = create_show(client)
    response = client.delete(f"/api/shows/{show_id}", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    assert repository.get_show(show_id) is not None


def test_a_change_from_the_ui_origin_is_allowed(client):
    show_id, (a, b, c) = three_breaks(client)
    response = client.delete(f"/api/shows/{show_id}/items/{a}", headers={"Origin": UI_ORIGIN})
    assert response.status_code == 200
    assert len(repository.list_items(show_id)) == 2


def test_a_read_from_another_origin_is_answered_without_cors_headers(client):
    response = client.get("/api/shows", headers={"Origin": "http://evil.example"})
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers


@pytest.mark.usefixtures("catalogue_down")
def test_the_503_carries_cors_headers_so_the_ui_can_show_it(client):
    show_id = save_show_with_song_7_and_a_break()
    response = client.post(
        f"/api/shows/{show_id}/songs", json={"song_id": 3}, headers={"Origin": UI_ORIGIN}
    )
    assert response.status_code == 503
    assert response.headers["Access-Control-Allow-Origin"] == UI_ORIGIN
