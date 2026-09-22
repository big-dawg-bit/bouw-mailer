"""Gedeelde fixtures.

De tests draaien op een zelfgemaakt Excel-bestand, niet op data/. Zo werken
ze ook op een verse clone, zonder de echte adressenlijst.
"""

import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HEADERS = [
    "Bedrijfsnaam",
    "Categorie",
    "Gemeente",
    "Plaats",
    "Adres",
    "Postcode",
    "KvK-nummer",
    "Website",
    "Telefoon",
    "Medewerkers",
    "Bron omvang",
    "Algemeen e-mail",
]

# (bedrijfsnaam, categorie, plaats, e-mail)
ROWS = [
    ("Bouwbedrijf Alfa", "aannemer", "Maastricht", "info@alfa.nl"),
    ("Bouwbedrijf Beta", "aannemer", "Meerssen", "info@beta.nl"),
    ("Architect Gamma", "architect", "Maastricht", "info@gamma.nl"),
    ("Ingenieurs Delta", "ingenieursbureau", "Eijsden", "info@delta.nl"),
    ("Ontwikkelaar Epsilon", "projectontwikkelaar", "Maastricht", "info@epsilon.nl"),
    ("Corporatie Zeta", "woningcorporatie", "Maastricht", "info@zeta.nl"),
    # Zelfde adres als Alfa -> moet samengevoegd worden, niet 2x gemaild.
    ("Bouwbedrijf Alfa Holding", "aannemer", "Maastricht", "info@alfa.nl"),
    # Zelfde adres, maar hogere variant -> opdrachtgever moet winnen van ontwerp.
    ("Gamma Ontwikkeling", "projectontwikkelaar", "Maastricht", "info@gamma.nl"),
    # Hoort overgeslagen te worden:
    ("Zonder Adres BV", "aannemer", "Maastricht", ""),
    ("Kapot Adres BV", "aannemer", "Maastricht", "geen-apenstaartje"),
    ("Onbekende Categorie BV", "sloopbedrijf", "Maastricht", "info@sloop.nl"),
]


def _write_sheet(path: Path, headers, rows) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Bedrijven"
    sheet.append(headers)
    index = {name: i for i, name in enumerate(headers)}
    for company, category, city, email in rows:
        line = [None] * len(headers)
        line[index["Bedrijfsnaam"]] = company
        line[index["Categorie"]] = category
        line[index["Plaats"]] = city
        line[index["Algemeen e-mail"]] = email
        sheet.append(line)
    # Tweede werkblad, zoals in het echte bestand.
    workbook.create_sheet("Toelichting").append(["Testbestand"])
    workbook.save(path)
    return path


@pytest.fixture
def sheet(tmp_path) -> Path:
    return _write_sheet(tmp_path / "test.xlsx", HEADERS, ROWS)


@pytest.fixture
def make_sheet(tmp_path):
    """Voor tests die een afwijkend bestand nodig hebben."""

    def _make(rows, headers=HEADERS, name="custom.xlsx"):
        return _write_sheet(tmp_path / name, headers, rows)

    return _make


@pytest.fixture
def config(tmp_path, sheet, monkeypatch):
    """Config die naar het testbestand wijst en nooit echt mailt."""
    monkeypatch.setenv("EXCEL_PATH", str(sheet))
    monkeypatch.setenv("SENT_LOG_PATH", str(tmp_path / "sent_log.csv"))
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "x" * 16)
    monkeypatch.setenv("FROM_NAME", "Testafzender")
    monkeypatch.setenv("REPLY_TO", "reply@example.com")
    monkeypatch.setenv("SEND_DELAY_SECONDS", "0")

    from config import Config

    return Config()


class FakeSender:
    """Vervangt de echte SMTP-verbinding. Onthoudt wat er 'verstuurd' is."""

    instances = []

    def __init__(self, config):
        self.config = config
        self.sent = []
        self.connected = False
        self.fail_for = set()
        FakeSender.instances.append(self)

    def __enter__(self):
        self.connected = True
        return self

    def send(self, message):
        to = message["To"]
        if to in self.fail_for:
            raise RuntimeError("mailbox full")
        self.sent.append(message)

    def __exit__(self, *exc_info):
        return False


@pytest.fixture
def fake_sender(monkeypatch):
    FakeSender.instances = []
    return FakeSender
