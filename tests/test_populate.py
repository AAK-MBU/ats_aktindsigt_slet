"""Tests af opbygningen af kø-items ud fra portalens kandidatliste."""

from types import SimpleNamespace

from ats_framework.processes import populate, slet_config

CANDIDATES = {
    "dage": 30,
    "frist": "2026-09-07T02:00:00+00:00",
    "kandidater": [
        {"sagId": 12, "behandlingsStatus": "Afsluttet", "afsluttetDato": "a"},
        {"sagId": 13, "behandlingsStatus": "Afvist", "afsluttetDato": "b"},
    ],
    "udenAfsluttetDato": [
        {"sagId": 3, "behandlingsStatus": "Afsluttet", "oprettelsesdato": "c"}
    ],
}


def test_dry_run_builds_one_report_item():
    items = populate.build_items(CANDIDATES, "2026-10-07", dry_run=True)
    assert [i["reference"] for i in items] == ["dryrun_2026-10-07"]
    data = items[0]["data"]
    assert data["type"] == "dry_run"
    assert [k["sagId"] for k in data["kandidater"]] == [12, 13]
    assert data["udenAfsluttetDato"] == CANDIDATES["udenAfsluttetDato"]


def test_live_builds_one_item_per_sag_and_a_report():
    items = populate.build_items(CANDIDATES, "2026-10-07", dry_run=False)
    assert [i["reference"] for i in items] == [
        "slet_sag_12",
        "slet_sag_13",
        "uden_dato_2026-10-07",
    ]
    assert items[0]["data"] == {
        "type": "slet_sag",
        "sagId": 12,
        "behandlingsStatus": "Afsluttet",
        "afsluttetDato": "a",
    }
    assert items[2]["data"]["sager"] == CANDIDATES["udenAfsluttetDato"]


def test_live_without_undated_sager_has_no_report():
    candidates = {**CANDIDATES, "udenAfsluttetDato": []}
    items = populate.build_items(candidates, "2026-10-07", dry_run=False)
    assert [i["reference"] for i in items] == ["slet_sag_12", "slet_sag_13"]


def test_live_with_nothing_builds_nothing():
    assert populate.build_items({"kandidater": []}, "2026-10-07", False) == []


def test_collect_items_uses_credential_and_mode(monkeypatch):
    monkeypatch.setattr(slet_config, "AKTINDSIGT_BASE_URL", "https://akt")
    monkeypatch.setattr(slet_config, "AKTINDSIGT_CREDENTIAL", "akt_slet")
    monkeypatch.setattr(slet_config, "DRY_RUN", False)
    monkeypatch.setattr(populate, "get_credential_password", lambda n: f"key:{n}")
    seen = {}

    def fake_fetch(api_key):
        seen["key"] = api_key
        return CANDIDATES

    monkeypatch.setattr(populate, "fetch_candidates", fake_fetch)
    items = populate.collect_items(SimpleNamespace(name="aktindsigt.slet"))
    assert seen["key"] == "key:akt_slet"
    assert items[0]["reference"] == "slet_sag_12"
