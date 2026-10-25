import sqlite3
import time

import jwt
import pytest

import keys
from app import app

 
@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch): #run each test against a fresh database in a tmp dir
    monkeypatch.chdir(tmp_path)
    keys.initialize_database()


def _database_rows():
    with sqlite3.connect(keys.DB_FILE) as connection:
        return connection.execute(
            "SELECT kid, key, exp FROM keys ORDER BY kid"
        ).fetchall()


def test_database_has_expected_schema_and_seed_keys():
    with sqlite3.connect(keys.DB_FILE) as connection:
        columns = connection.execute("PRAGMA table_info(keys)").fetchall()

    assert [column[1] for column in columns] == ["kid", "key", "exp"]

    now = int(time.time())
    rows = _database_rows()

    assert any(row[2] <= now for row in rows)
    assert any(row[2] >= now + 3600 for row in rows)
    assert all(isinstance(row[1], bytes) for row in rows)


def test_jwks_returns_only_non_expired_keys():
    client = app.test_client()
    response = client.get("/.well-known/jwks.json")

    assert response.status_code == 200
    data = response.get_json()
    assert "keys" in data

    now = int(time.time())
    valid_ids = {str(row[0]) for row in _database_rows() if row[2] > now}
    returned_ids = {jwk["kid"] for jwk in data["keys"]}

    assert returned_ids == valid_ids
    assert all(jwk["kty"] == "RSA" for jwk in data["keys"])
    assert all(jwk["alg"] == "RS256" for jwk in data["keys"])


def test_auth_returns_valid_database_backed_token():
    client = app.test_client()
    response = client.post("/auth")

    assert response.status_code == 200
    token = response.get_data(as_text=True)
    header = jwt.get_unverified_header(token)
    payload = jwt.decode(
        token,
        options={"verify_signature": False, "verify_exp": False},
    )

    rows_by_id = {str(row[0]): row for row in _database_rows()}
    database_row = rows_by_id[header["kid"]]

    assert header["alg"] == "RS256"
    assert payload["sub"] == "fake-user"
    assert payload["exp"] == database_row[2]
    assert payload["exp"] > int(time.time())


def test_auth_expired_uses_expired_database_key():
    client = app.test_client()
    response = client.post("/auth?expired=true")

    assert response.status_code == 200
    token = response.get_data(as_text=True)
    header = jwt.get_unverified_header(token)
    payload = jwt.decode(
        token,
        options={"verify_signature": False, "verify_exp": False},
    )

    rows_by_id = {str(row[0]): row for row in _database_rows()}
    database_row = rows_by_id[header["kid"]]

    assert header["alg"] == "RS256"
    assert payload["sub"] == "fake-user"
    assert payload["exp"] == database_row[2]
    assert payload["exp"] <= int(time.time())


def test_expired_parameter_presence_selects_expired_key():
    client = app.test_client()
    response = client.post("/auth?expired=false")

    token = response.get_data(as_text=True)
    payload = jwt.decode(
        token,
        options={"verify_signature": False, "verify_exp": False},
    )

    assert payload["exp"] <= int(time.time())


def test_auth_accepts_mock_basic_auth_and_json_body():
    client = app.test_client()

    basic_response = client.post(
        "/auth",
        headers={"Authorization": "Basic dXNlckFCQzpwYXNzd29yZDEyMw=="},
    )
    json_response = client.post(
        "/auth",
        json={"username": "userABC", "password": "password123"},
    )

    assert basic_response.status_code == 200
    assert json_response.status_code == 200
    assert jwt.get_unverified_header(basic_response.get_data(as_text=True))["kid"]
    assert jwt.get_unverified_header(json_response.get_data(as_text=True))["kid"]
