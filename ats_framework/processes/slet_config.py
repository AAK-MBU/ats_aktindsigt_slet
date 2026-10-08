"""Konfiguration af sletteprocessen: portalens backend, dry-run og mails.

Reglen for, hvornår en sag er gammel nok til at blive slettet, ligger i
aktindsigt-portalens backend og kan ikke ændres herfra. Værdier med præfikset
``UDFYLDES_`` er pladsholdere. ``validate_config`` afviser dem, så en kørsel
fejler højlydt, indtil de er udfyldt.
"""

PLACEHOLDER_PREFIX = "UDFYLDES_"

PROCESS_NAME = "ats_aktindsigt_slet"

# Med DRY_RUN sletter processen intet. Populate lægger ét rapport-item i køen,
# og behandlingen af det mailer listen over de sager, der ville blive slettet.
DRY_RUN = True

# Aktindsigt-portalens backend. Endpointene under /api/sletning lægges til.
AKTINDSIGT_BASE_URL = "https://mbu-aktindsigt.adm.aarhuskommune.dk"
# Credential i rpa.Credentials, hvis password er portalens slette-API-nøgle
# (sendes i headeren X-API-Key og valideres mod SLETNING_API_KEYS i portalen).
AKTINDSIGT_CREDENTIAL = "aktindsigt_sletning_api_key"

# Timeout i sekunder pr. kald til portalen. En sletning fjerner både
# databaserækker og sagens dokumentmappe og kan derfor tage tid.
REQUEST_TIMEOUT = 300

# ----------------------
# Rapport-mails (navne på konstanter i rpa.Constants)
# ----------------------
RECIPIENTS_CONSTANT = "E-mail"  # JSON-liste eller kommasepareret
SENDER_CONSTANT = "e-mail_noreply"
SMTP_SERVER_CONSTANT = "smtp_adm_server"
SMTP_PORT_CONSTANT = "smtp_port"

SUBJECT_PREFIX = "Aktindsigt sletning"
# Emneskabeloner. Formatteres med item'ets felter.
SUBJECTS = {
    "dry_run": "Dry-run {dato}: {antal} sager ville blive slettet",
    "uden_dato": "{antal} afsluttede sager uden afslutningsdato slettes ikke",
}


def subject(key: str, **fields: object) -> str:
    """Bygger emnelinjen for en rapport-mail.

    Args:
        key: Nøglen i ``SUBJECTS``.
        **fields: Værdierne, skabelonen formatteres med.

    Returns:
        ``SUBJECT_PREFIX`` efterfulgt af den formatterede skabelon.
    """
    return f"{SUBJECT_PREFIX}: {SUBJECTS[key].format(**fields)}"


def validate_config() -> None:
    """Afviser konfiguration med pladsholdere.

    Raises:
        ValueError: Hvis portalens adresse eller credential-navnet er en
            pladsholder.
    """
    values = [AKTINDSIGT_BASE_URL, AKTINDSIGT_CREDENTIAL]
    placeholders = [v for v in values if v.startswith(PLACEHOLDER_PREFIX)]
    if placeholders:
        raise ValueError(f"slet_config contains unfilled placeholders: {placeholders}")
