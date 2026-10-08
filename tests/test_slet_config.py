"""Tests af valideringen af slette-konfigurationen."""

import pytest

from ats_framework.processes import slet_config


def test_placeholders_are_rejected():
    with pytest.raises(ValueError, match="UDFYLDES_"):
        slet_config.validate_config()


def test_filled_config_passes(monkeypatch):
    monkeypatch.setattr(slet_config, "AKTINDSIGT_BASE_URL", "https://akt")
    monkeypatch.setattr(slet_config, "AKTINDSIGT_CREDENTIAL", "akt_slet")
    slet_config.validate_config()


def test_dry_run_is_default():
    assert slet_config.DRY_RUN is True
