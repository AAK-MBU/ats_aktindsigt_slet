"""Tests af kaldene til portalens slette-API."""

import pytest
import requests

from ats_framework.helpers import aktindsigt_api
from ats_framework.processes import slet_config


class _Response:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


@pytest.fixture(autouse=True)
def base_url(monkeypatch):
    monkeypatch.setattr(slet_config, "AKTINDSIGT_BASE_URL", "https://akt/")


def test_fetch_candidates(monkeypatch):
    seen = {}

    def fake_get(url, headers, timeout):
        seen.update(url=url, headers=headers, timeout=timeout)
        return _Response(payload={"kandidater": [], "udenAfsluttetDato": []})

    monkeypatch.setattr(aktindsigt_api.requests, "get", fake_get)
    assert aktindsigt_api.fetch_candidates("k")["kandidater"] == []
    assert seen["url"] == "https://akt/api/sletning/kandidater"
    assert seen["headers"] == {"X-API-Key": "k"}
    assert seen["timeout"] == slet_config.REQUEST_TIMEOUT


def _fake_delete(response, seen):
    def fake(url, headers, timeout):
        seen.update(url=url, headers=headers, timeout=timeout)
        return response

    return fake


def test_delete_sag_ok(monkeypatch):
    seen = {}
    payload = {"sagId": 7, "status": "slettet"}
    monkeypatch.setattr(
        aktindsigt_api.requests, "delete", _fake_delete(_Response(200, payload), seen)
    )
    assert aktindsigt_api.delete_sag(7, "k") == payload
    assert seen["url"] == "https://akt/api/sletning/sager/7"
    assert seen["headers"] == {"X-API-Key": "k"}


@pytest.mark.parametrize("code", [404, 409])
def test_delete_sag_refused(monkeypatch, code):
    response = _Response(code, {"detail": "for ny"})
    monkeypatch.setattr(aktindsigt_api.requests, "delete", _fake_delete(response, {}))
    with pytest.raises(aktindsigt_api.DeleteRefused) as exc:
        aktindsigt_api.delete_sag(7, "k")
    assert exc.value.status_code == code
    assert exc.value.detail == "for ny"


def test_delete_sag_refused_without_json(monkeypatch):
    response = _Response(409, None, text="conflict")
    monkeypatch.setattr(aktindsigt_api.requests, "delete", _fake_delete(response, {}))
    with pytest.raises(aktindsigt_api.DeleteRefused, match="conflict"):
        aktindsigt_api.delete_sag(7, "k")


def test_delete_sag_server_error_raises(monkeypatch):
    monkeypatch.setattr(
        aktindsigt_api.requests, "delete", _fake_delete(_Response(500), {})
    )
    with pytest.raises(requests.HTTPError):
        aktindsigt_api.delete_sag(7, "k")
