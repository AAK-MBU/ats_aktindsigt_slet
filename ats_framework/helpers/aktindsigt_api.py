"""Kald til aktindsigt-portalens slette-API.

Alle kald går til ``{AKTINDSIGT_BASE_URL}/api/sletning`` med headeren
``X-API-Key``. Portalen afgør selv, hvilke sager der er gamle nok til at blive
slettet, og tjekker reglen igen ved hver sletning.
"""

import logging

import requests

from ats_framework.processes import slet_config

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"


class DeleteRefused(Exception):
    """Portalen afviste at slette sagen.

    Attributes:
        status_code: 409 når sagen ikke opfylder slettereglen, 404 når sagen
            hverken findes eller er slettet før.
        detail: Portalens begrundelse.
    """

    def __init__(self, status_code: int, detail: str):
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _url(path: str) -> str:
    """Bygger den fulde adresse til et endpoint under ``/api/sletning``."""
    return f"{slet_config.AKTINDSIGT_BASE_URL.rstrip('/')}/api/sletning/{path}"


def fetch_candidates(api_key: str) -> dict:
    """Henter de sager, portalen anser som klar til sletning.

    Kalder ``GET /api/sletning/kandidater``.

    Args:
        api_key: Portalens slette-API-nøgle.

    Returns:
        Svaret som dict med nøglerne:
            ``dage``: Antal dage efter afslutning, en sag gemmes.
            ``frist``: Skæringstidspunktet (ISO-8601, UTC).
            ``kandidater``: Liste af ``{"sagId", "behandlingsStatus",
            "afsluttetDato"}`` for sager afsluttet eller afvist før fristen.
            ``udenAfsluttetDato``: Liste af ``{"sagId",
            "behandlingsStatus", "oprettelsesdato"}`` for afsluttede eller
            afviste sager uden afslutningsdato. De slettes ikke.

    Raises:
        requests.HTTPError: Hvis portalen afviser kaldet.
    """
    response = requests.get(
        _url("kandidater"),
        headers={API_KEY_HEADER: api_key},
        timeout=slet_config.REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    logger.info(
        "Portal reports %d candidates and %d closed sager without date",
        len(body.get("kandidater") or []),
        len(body.get("udenAfsluttetDato") or []),
    )
    return body


def delete_sag(sag_id: int, api_key: str) -> dict:
    """Beder portalen slette en sag med databaserækker og dokumentmappe.

    Kalder ``DELETE /api/sletning/sager/{sag_id}``. Kaldet kan gentages: en
    halvt gennemført sletning gøres færdig, og en sag der allerede er slettet,
    giver status ``allerede_slettet``.

    Args:
        sag_id: Sagens id i portalen.
        api_key: Portalens slette-API-nøgle.

    Returns:
        Svaret som dict med nøglerne ``sagId``, ``status`` (``slettet`` eller
        ``allerede_slettet``), ``databaseraekker``, ``filer`` og
        ``sletningId``.

    Raises:
        DeleteRefused: Hvis portalen svarer 409 eller 404.
        requests.HTTPError: Ved andre fejlsvar.
    """
    response = requests.delete(
        _url(f"sager/{sag_id}"),
        headers={API_KEY_HEADER: api_key},
        timeout=slet_config.REQUEST_TIMEOUT,
    )
    if response.status_code in (404, 409):
        try:
            detail = str(response.json().get("detail") or "")
        except ValueError:
            detail = response.text
        raise DeleteRefused(response.status_code, detail)
    response.raise_for_status()
    return response.json()
