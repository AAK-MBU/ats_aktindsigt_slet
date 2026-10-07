"""Behandler sletteprocessens items: sletter sager og sender rapporter."""

import logging
from html import escape

from mbu_rpa_core.exceptions import BusinessError

from ats_framework.helpers.aktindsigt_api import DeleteRefused, delete_sag
from ats_framework.helpers.email import send_report_email
from ats_framework.helpers.rpa_db import get_credential_password
from ats_framework.processes import slet_config

logger = logging.getLogger(__name__)


def _table(headers: list[str], rows: list[list]) -> str:
    """Bygger en HTML-tabel med escapede værdier."""
    head = "".join(f"<th align='left'>{escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row) + "</tr>"
        for row in rows
    )
    return f"<table border='1' cellpadding='4' cellspacing='0'><tr>{head}</tr>{body}</table>"


def _uden_dato_html(sager: list[dict]) -> str:
    """Bygger afsnittet om afsluttede sager uden afslutningsdato."""
    return (
        f"<p>{len(sager)} sager er afsluttet eller afvist, men har ingen "
        "afslutningsdato. De slettes ikke automatisk og skal vurderes manuelt.</p>"
        + _table(
            ["Sag-id", "Status", "Oprettet"],
            [
                [s.get("sagId"), s.get("behandlingsStatus"), s.get("oprettelsesdato")]
                for s in sager
            ],
        )
    )


def handle_slet_sag(data: dict) -> str:
    """Sletter én sag i portalen.

    Args:
        data: Item'ets data med nøglen ``sagId``.

    Returns:
        Besked til det gennemførte item med portalens resultat.

    Raises:
        BusinessError: Hvis portalen afviser sletningen (409: sagen opfylder
            ikke slettereglen, 404: sagen findes ikke).
    """
    sag_id = data["sagId"]
    api_key = get_credential_password(slet_config.AKTINDSIGT_CREDENTIAL)
    try:
        result = delete_sag(sag_id, api_key)
    except DeleteRefused as e:
        raise BusinessError(
            f"Portalen afviste sletning af sag {sag_id} ({e.status_code}): {e.detail}"
        ) from e

    message = (
        f"Sag {sag_id}: {result.get('status')}, "
        f"{result.get('databaseraekker')} databaserækker, "
        f"{result.get('filer')} filer, sletning {result.get('sletningId')}"
    )
    logger.info(message)
    return message


def handle_dry_run(data: dict) -> str:
    """Mailer listen over de sager, en rigtig kørsel ville slette.

    Args:
        data: Item'ets data fra ``populate.build_items`` med ``dry_run``.

    Returns:
        Besked til det gennemførte item.
    """
    kandidater = data.get("kandidater") or []
    uden_dato = data.get("udenAfsluttetDato") or []
    html = (
        "<p>Sletteprocessen kører i dry-run og har ikke slettet noget. "
        f"Med sletning slået til ville {len(kandidater)} sager blive slettet: "
        f"sager afsluttet eller afvist for mindst {escape(str(data.get('dage')))} "
        f"dage siden (før {escape(str(data.get('frist')))}).</p>"
        + _table(
            ["Sag-id", "Status", "Afsluttet"],
            [
                [k.get("sagId"), k.get("behandlingsStatus"), k.get("afsluttetDato")]
                for k in kandidater
            ],
        )
    )
    if uden_dato:
        html += _uden_dato_html(uden_dato)

    send_report_email(
        slet_config.subject("dry_run", dato=data.get("dato"), antal=len(kandidater)),
        html,
    )
    return f"Dry-run: {len(kandidater)} kandidater, {len(uden_dato)} uden dato"


def handle_uden_dato(data: dict) -> str:
    """Mailer listen over afsluttede sager uden afslutningsdato.

    Args:
        data: Item'ets data fra ``populate.build_items`` med ``sager``.

    Returns:
        Besked til det gennemførte item.
    """
    sager = data.get("sager") or []
    send_report_email(
        slet_config.subject("uden_dato", antal=len(sager)), _uden_dato_html(sager)
    )
    return f"Rapporteret {len(sager)} sager uden afslutningsdato"


HANDLERS = {
    "slet_sag": handle_slet_sag,
    "dry_run": handle_dry_run,
    "uden_dato": handle_uden_dato,
}


def handle_item(item_data: dict, item_reference: str) -> str:
    """Sender et item til handleren for dets type.

    Args:
        item_data: Item'ets data med nøglen ``type``.
        item_reference: Item'ets reference.

    Returns:
        Handlerens besked til det gennemførte item.

    Raises:
        BusinessError: Hvis item'ets type er ukendt, eller portalen afviser en
            sletning.
    """
    handler = HANDLERS.get(item_data.get("type", "no type defined"))
    if handler is None:
        raise BusinessError(
            f"Unknown item type {item_data.get('type')!r} for {item_reference}"
        )
    message = handler(item_data)
    logger.info("Handled item %s", item_reference)
    return message
