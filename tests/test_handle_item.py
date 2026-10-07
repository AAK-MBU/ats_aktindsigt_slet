"""Tests af behandlingen af sletteprocessens items."""

import pytest
import requests
from mbu_rpa_core.exceptions import BusinessError

from ats_framework.helpers.aktindsigt_api import DeleteRefused
from ats_framework.processes import handle_item, slet_config


@pytest.fixture
def mails(monkeypatch):
    sent = []
    monkeypatch.setattr(
        handle_item, "send_report_email", lambda s, h: sent.append((s, h))
    )
    monkeypatch.setattr(handle_item, "get_credential_password", lambda _n: "k")
    return sent


def _delete_returning(monkeypatch, outcome):
    def fake(sag_id, api_key):
        assert api_key == "k"
        if isinstance(outcome, Exception):
            raise outcome
        return {**outcome, "sagId": sag_id}

    monkeypatch.setattr(handle_item, "delete_sag", fake)


def test_slet_sag_ok(monkeypatch, mails):
    _delete_returning(
        monkeypatch,
        {"status": "slettet", "databaseraekker": 9, "filer": 4, "sletningId": 1},
    )
    message = handle_item.handle_item({"type": "slet_sag", "sagId": 7}, "slet_sag_7")
    assert message == "Sag 7: slettet, 9 databaserækker, 4 filer, sletning 1"
    assert mails == []


@pytest.mark.parametrize("code", [404, 409])
def test_slet_sag_refused_is_business_error(monkeypatch, mails, code):
    _delete_returning(monkeypatch, DeleteRefused(code, "for ny"))
    with pytest.raises(BusinessError, match="for ny"):
        handle_item.handle_item({"type": "slet_sag", "sagId": 7}, "slet_sag_7")
    assert mails == []


@pytest.mark.usefixtures("mails")
def test_slet_sag_server_error_propagates(monkeypatch):
    _delete_returning(monkeypatch, requests.HTTPError("500"))
    with pytest.raises(requests.HTTPError):
        handle_item.handle_item({"type": "slet_sag", "sagId": 7}, "slet_sag_7")


def test_dry_run_mails_candidates_and_undated(mails):
    data = {
        "type": "dry_run",
        "dato": "2026-10-07",
        "dage": 30,
        "frist": "2026-09-07",
        "kandidater": [{"sagId": 12, "behandlingsStatus": "Afvist"}],
        "udenAfsluttetDato": [{"sagId": 3, "behandlingsStatus": "Afsluttet"}],
    }
    message = handle_item.handle_item(data, "dryrun_2026-10-07")
    assert message == "Dry-run: 1 kandidater, 1 uden dato"
    subject, html = mails[0]
    assert subject.startswith(slet_config.SUBJECT_PREFIX)
    assert "1 sager ville blive slettet" in subject
    assert "<td>12</td>" in html and "<td>3</td>" in html


def test_uden_dato_mails_list(mails):
    data = {"type": "uden_dato", "sager": [{"sagId": 3, "oprettelsesdato": "<x>"}]}
    handle_item.handle_item(data, "uden_dato_2026-10-07")
    subject, html = mails[0]
    assert "1 afsluttede sager" in subject
    assert "&lt;x&gt;" in html


@pytest.mark.usefixtures("mails")
def test_unknown_type_is_business_error():
    with pytest.raises(BusinessError):
        handle_item.handle_item({"type": "nope"}, "ref")
