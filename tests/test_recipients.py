"""Tests voor het inlezen en ontdubbelen van de adressenlijst."""

import pytest

from recipients import load_recipients


def test_dedupe_geen_enkel_adres_dubbel(sheet):
    """De kern: geen enkel adres mag twee keer in de lijst staan."""
    report = load_recipients(sheet)
    adressen = [r.email.lower() for r in report.recipients]
    assert len(adressen) == len(set(adressen)), f"dubbele adressen: {adressen}"


def test_gedeeld_adres_wordt_samengevoegd(sheet):
    report = load_recipients(sheet)
    alfa = [r for r in report.recipients if r.email == "info@alfa.nl"]
    assert len(alfa) == 1
    # Het tweede bedrijf op dat adres wordt onthouden, maar krijgt geen eigen mail.
    assert "Bouwbedrijf Alfa Holding" in alfa[0].also


def test_hoogste_variant_wint_bij_botsing(sheet):
    """info@gamma.nl is zowel architect (ontwerp) als ontwikkelaar
    (opdrachtgever). opdrachtgever staat hoger, dus die wint."""
    report = load_recipients(sheet)
    gamma = next(r for r in report.recipients if r.email == "info@gamma.nl")
    assert gamma.variant == "opdrachtgever"


def test_rij_zonder_adres_wordt_overgeslagen(sheet):
    report = load_recipients(sheet)
    assert report.skipped_no_email == 1
    assert all(r.company != "Zonder Adres BV" for r in report.recipients)


def test_ongeldig_adres_wordt_overgeslagen(sheet):
    report = load_recipients(sheet)
    assert [c for c, _ in report.skipped_bad_email] == ["Kapot Adres BV"]


def test_onbekende_categorie_wordt_overgeslagen(sheet):
    """Liever overslaan dan gokken welke tekst iemand moet krijgen."""
    report = load_recipients(sheet)
    assert [c for c, _ in report.skipped_unknown_category] == ["Onbekende Categorie BV"]
    assert all(r.email != "info@sloop.nl" for r in report.recipients)


def test_juiste_variant_per_categorie(sheet):
    report = load_recipients(sheet)
    per_adres = {r.email: r.variant for r in report.recipients}
    assert per_adres["info@alfa.nl"] == "uitvoerend"       # aannemer
    assert per_adres["info@delta.nl"] == "ontwerp"          # ingenieursbureau
    assert per_adres["info@epsilon.nl"] == "opdrachtgever"  # projectontwikkelaar
    assert per_adres["info@zeta.nl"] == "opdrachtgever"     # woningcorporatie


def test_bedrijfsnaam_en_plaats_blijven_kloppen(sheet):
    """Naamfouten voorkomen: de naam uit het bestand moet 1-op-1 meekomen."""
    report = load_recipients(sheet)
    delta = next(r for r in report.recipients if r.email == "info@delta.nl")
    assert delta.company == "Ingenieurs Delta"
    assert delta.city == "Eijsden"
    assert delta.category == "ingenieursbureau"


def test_kolommen_op_naam_niet_op_positie(make_sheet):
    """Het bronbestand wordt periodiek opnieuw gegenereerd; als kolommen
    verschuiven mag dat de mailing niet omgooien."""
    door_elkaar = ["Telefoon", "Algemeen e-mail", "Plaats", "Bedrijfsnaam", "Categorie"]
    path = make_sheet(
        [("Bouwbedrijf Alfa", "aannemer", "Maastricht", "info@alfa.nl")],
        headers=door_elkaar,
    )
    report = load_recipients(path)
    assert len(report.recipients) == 1
    assert report.recipients[0].company == "Bouwbedrijf Alfa"
    assert report.recipients[0].email == "info@alfa.nl"


def test_ontbrekende_kolom_geeft_nette_fout(make_sheet):
    path = make_sheet([], headers=["Bedrijfsnaam", "Categorie"])
    with pytest.raises(SystemExit) as exc:
        load_recipients(path)
    assert "Algemeen e-mail" in str(exc.value)


def test_ontbrekend_bestand_geeft_nette_fout(tmp_path):
    with pytest.raises(SystemExit) as exc:
        load_recipients(tmp_path / "bestaat-niet.xlsx")
    assert "niet gevonden" in str(exc.value)


def test_spaties_rond_adres_worden_weggehaald(make_sheet):
    path = make_sheet([("Spatie BV", "aannemer", "Maastricht", "  info@spatie.nl  ")])
    report = load_recipients(path)
    assert report.recipients[0].email == "info@spatie.nl"


def test_hoofdletters_tellen_als_hetzelfde_adres(make_sheet):
    """INFO@ALFA.NL en info@alfa.nl zijn dezelfde mailbox."""
    path = make_sheet(
        [
            ("Alfa Een", "aannemer", "Maastricht", "info@alfa.nl"),
            ("Alfa Twee", "aannemer", "Maastricht", "INFO@ALFA.NL"),
        ]
    )
    report = load_recipients(path)
    assert len(report.recipients) == 1
