"""Tests for the show pages when the catalogue service is down.

The catalogue_down fixture from conftest.py makes every catalogue call
fail, as if the container were stopped. The pages must still answer, with
a notice, never a 500.
"""
import pytest

import main
from shows import repository


@pytest.fixture
def client(database):
    """A Flask test client on a fresh database."""
    return main.create_app().test_client()


def create_show_with_one_song():
    """Save a show with song 7 and a break, without the catalogue."""
    show_id = repository.insert_show(
        {"name": "Halloween night", "venue": "Teatro Real", "show_date": "2026-10-31", "max_minutes": 90}
    )
    repository.insert_song_item(show_id, 1, 7)
    repository.insert_break_item(show_id, 2, "Rest", 60)
    return show_id


@pytest.mark.usefixtures("catalogue_down")
def test_show_page_shows_a_notice_when_the_catalogue_is_down(client):
    show_id = create_show_with_one_song()
    response = client.get(f"/shows/{show_id}")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Catalogue service unavailable" in page
    assert "Song details unavailable (id 7)" in page
    assert "Break: Rest" in page
    assert "Checks skipped" in page


@pytest.mark.usefixtures("catalogue_down")
def test_adding_a_song_when_the_catalogue_is_down_shows_why_it_was_refused(client):
    show_id = create_show_with_one_song()
    response = client.post(f"/shows/{show_id}/songs", data={"song_id": "3"})
    assert response.status_code == 200
    assert "the song could not be checked and was not added" in response.get_data(as_text=True)
    assert len(repository.list_items(show_id)) == 2


@pytest.mark.usefixtures("catalogue_down")
def test_shows_list_and_health_work_when_the_catalogue_is_down(client):
    create_show_with_one_song()
    assert client.get("/shows/").status_code == 200
    assert client.get("/health").status_code == 200
