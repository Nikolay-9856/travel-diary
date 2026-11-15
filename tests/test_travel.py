import io
import os
import tempfile

import pytest

from app import app, init_db

TRIP = {"title": "Байкал зимой", "place": "Листвянка", "lat": "51.8536", "lon": "104.8643",
        "date_from": "2026-02-10", "date_to": "2026-02-17", "description": "Лёд и нерпы",
        "cost": "85000", "currency": "RUB", "r_transport": "3", "r_safety": "5",
        "r_crowd": "4", "r_nature": "5", "is_public": "1"}


@pytest.fixture
def client(tmp_path):
    fd, path = tempfile.mkstemp()
    app.config.update(TESTING=True, DATABASE=path, UPLOAD_DIR=str(tmp_path))
    with app.app_context():
        init_db()
    with app.test_client() as c:
        yield c
    os.close(fd)
    os.unlink(path)


def user(c, name):
    c.post("/register", data={"username": name, "display_name": name.title(), "password": "secret1"})
    c.post("/login", data={"username": name, "password": "secret1"})


def test_create_trip_with_location_cost_ratings(client):
    user(client, "masha")
    r = client.post("/trip/new", data=TRIP)
    assert r.status_code == 302
    page = client.get("/trip/1").get_data(as_text=True)
    assert "Листвянка" in page and "85 000 RUB" in page and "51.85360" in page
    pts = client.get("/api/trips").get_json()
    assert pts[0]["lat"] == 51.8536


def test_photo_upload_and_type_check(client):
    user(client, "masha")
    data = dict(TRIP)
    data["photos"] = [(io.BytesIO(b"\x89PNG fake"), "lake.png"), (io.BytesIO(b"MZ"), "virus.exe")]
    r = client.post("/trip/new", data=data, content_type="multipart/form-data", follow_redirects=True)
    text = r.get_data(as_text=True)
    assert "virus.exe пропущен" in text
    assert text.count("/uploads/") >= 1


def test_validation(client):
    user(client, "masha")
    bad = dict(TRIP, lat="120", cost="-1")
    text = client.post("/trip/new", data=bad).get_data(as_text=True)
    assert "Широта" in text and "отрицательной" in text


def test_other_users_see_public_only(client):
    user(client, "masha")
    client.post("/trip/new", data=TRIP)
    client.post("/trip/new", data=dict(TRIP, title="Личная поездка", is_public=""))
    client.get("/logout")
    user(client, "petya")
    page = client.get("/").get_data(as_text=True)
    assert "Байкал зимой" in page and "Личная поездка" not in page
    assert client.get("/trip/2").status_code == 404
    assert client.post("/trip/1/delete").status_code == 403


def test_owner_edit_and_delete(client):
    user(client, "masha")
    client.post("/trip/new", data=TRIP)
    client.post("/trip/1/edit", data=dict(TRIP, title="Байкал, обновлено"))
    assert "Байкал, обновлено" in client.get("/trip/1").get_data(as_text=True)
    client.post("/trip/1/delete")
    assert client.get("/trip/1").status_code == 404


def test_sort_by_cost(client):
    user(client, "masha")
    client.post("/trip/new", data=dict(TRIP, title="Дорогая", cost="200000"))
    client.post("/trip/new", data=dict(TRIP, title="Дешёвая", cost="5000"))
    page = client.get("/?sort=cheap").get_data(as_text=True)
    assert page.index("Дешёвая") < page.index("Дорогая")
