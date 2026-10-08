"""Samler items til sletteprocessens kø ud fra portalens kandidatliste."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from automation_server_client import Workqueue

from ats_framework.helpers.aktindsigt_api import fetch_candidates
from ats_framework.helpers.rpa_db import get_credential_password
from ats_framework.processes import slet_config

logger = logging.getLogger(__name__)


def build_items(candidates: dict, today: str, dry_run: bool) -> list[dict]:
    """Bygger kø-items ud fra portalens kandidatliste.

    Med ``dry_run`` bygges ét item ``dryrun_<dato>`` af typen ``dry_run`` med
    både kandidaterne og sagerne uden afslutningsdato. Ellers bygges ét item
    ``slet_sag_<sagId>`` af typen ``slet_sag`` pr. kandidat og, når der er
    sager uden afslutningsdato, ét item ``uden_dato_<dato>`` af typen
    ``uden_dato``.

    Args:
        candidates: Svaret fra ``fetch_candidates``.
        today: Kørselsdatoen som ``YYYY-MM-DD``. Indgår i referencerne på
            rapport-items, så de oprettes én gang pr. dag.
        dry_run: Om processen kun skal rapportere.

    Returns:
        Items som ``{"reference": ..., "data": ...}``.
    """
    kandidater = candidates.get("kandidater") or []
    uden_dato = candidates.get("udenAfsluttetDato") or []

    if dry_run and len(kandidater + uden_dato) > 0:
        return [
            {
                "reference": f"dryrun_{today}",
                "data": {
                    "type": "dry_run",
                    "dato": today,
                    "dage": candidates.get("dage"),
                    "frist": candidates.get("frist"),
                    "kandidater": kandidater,
                    "udenAfsluttetDato": uden_dato,
                },
            }
        ]

    items = [
        {
            "reference": f"slet_sag_{k['sagId']}",
            "data": {
                "type": "slet_sag",
                "sagId": k["sagId"],
                "behandlingsStatus": k.get("behandlingsStatus"),
                "afsluttetDato": k.get("afsluttetDato"),
            },
        }
        for k in kandidater
    ]
    if uden_dato:
        items.append(
            {
                "reference": f"uden_dato_{today}",
                "data": {"type": "uden_dato", "dato": today, "sager": uden_dato},
            }
        )
    return items


def collect_items(workqueue: Workqueue) -> list[dict]:
    """Henter kandidatlisten fra portalen og bygger kø-items.

    Args:
        workqueue: Sletteprocessens kø.

    Returns:
        Items som ``{"reference": ..., "data": ...}``.

    Raises:
        ValueError: Hvis ``slet_config`` indeholder pladsholdere.
        requests.HTTPError: Hvis portalen afviser kaldet.
    """
    slet_config.validate_config()
    api_key = get_credential_password(slet_config.AKTINDSIGT_CREDENTIAL)
    candidates = fetch_candidates(api_key)
    today = datetime.now(ZoneInfo("Europe/Copenhagen")).date().isoformat()

    items = build_items(candidates, today, slet_config.DRY_RUN)
    logger.info(
        "Built %d items for %s (dry run: %s)",
        len(items),
        workqueue.name,
        slet_config.DRY_RUN,
    )
    return items
