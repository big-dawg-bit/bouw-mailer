"""Configuratie: leest .env en houdt de categorie-indeling vast."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
SENT_LOG = BASE_DIR / "sent_log.csv"

load_dotenv(BASE_DIR / ".env")

# Welke kolomkoppen we uit het Excel-bestand nodig hebben.
COL_COMPANY = "Bedrijfsnaam"
COL_CATEGORY = "Categorie"
COL_EMAIL = "Algemeen e-mail"
COL_CITY = "Plaats"
SHEET_NAME = "Bedrijven"

# Categorie (kolom B) -> welke template het bedrijf krijgt.
# Wil je de indeling anders? Pas alleen deze dict aan.
CATEGORY_VARIANTS = {
    "aannemer": "uitvoerend",
    "architect": "ontwerp",
    "ingenieursbureau": "ontwerp",
    "projectontwikkelaar": "opdrachtgever",
    "projectontwikkelaar/belegger": "opdrachtgever",
    "woningcorporatie": "opdrachtgever",
}

# Sommige bedrijven delen een e-mailadres (hetzelfde adres kan 4x voorkomen, over twee
# varianten heen). Bij zo'n botsing wint de variant die hier het hoogst staat.
VARIANT_PRIORITY = ["opdrachtgever", "ontwerp", "uitvoerend"]

VARIANTS = VARIANT_PRIORITY


class Config:
    """Instellingen uit .env.

    Het inlezen mag altijd; pas require_smtp() klaagt over ontbrekende
    inloggegevens. Zo draait een dry-run ook zonder ingevulde .env.
    """

    def __init__(self) -> None:
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = (os.getenv("SMTP_USER") or "").strip()
        self.smtp_password = (os.getenv("SMTP_PASSWORD") or "").replace(" ", "")
        self.from_name = (os.getenv("FROM_NAME") or "").strip()
        self.reply_to = (os.getenv("REPLY_TO") or "").strip() or self.smtp_user
        self.send_delay = float(os.getenv("SEND_DELAY_SECONDS", "8"))

        excel = os.getenv("EXCEL_PATH", "data/emailaddressen-bouwbedrijven.xlsx")
        self.excel_path = (BASE_DIR / excel).resolve()

    def require_smtp(self) -> None:
        """Roep dit aan vlak voordat er echt verstuurd wordt."""
        if not (BASE_DIR / ".env").exists():
            sys.exit(
                "FOUT: geen .env gevonden.\n"
                "      Doe eerst:  cp .env.example .env   en vul hem in."
            )

        missing = [
            key
            for key, value in (
                ("SMTP_HOST", self.smtp_host),
                ("SMTP_USER", self.smtp_user),
                ("SMTP_PASSWORD", self.smtp_password),
                ("FROM_NAME", self.from_name),
            )
            if not value
        ]
        if missing:
            sys.exit(
                "FOUT: deze waarden ontbreken in .env: " + ", ".join(missing)
            )

        # Een App Password is 16 tekens; Google toont hem met spaties erin.
        if "gmail" in self.smtp_host and len(self.smtp_password) != 16:
            print(
                f"LET OP: SMTP_PASSWORD is {len(self.smtp_password)} tekens. Een "
                f"Google App Password is er 16. Je gewone wachtwoord werkt niet.",
                file=sys.stderr,
            )

    @property
    def from_header(self) -> str:
        return f"{self.from_name} <{self.smtp_user}>"
