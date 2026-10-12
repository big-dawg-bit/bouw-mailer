"""Opbouw van de mail: afbeelding onderaan en bijlagen per variant."""

import mailer
from recipients import Recipient


def _recipient(variant="uitvoerend"):
    return Recipient("info@alfa.nl", "Alfa", "aannemer", "Maastricht", variant, [])


def _use_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(mailer, "TEMPLATE_DIR", tmp_path)
    monkeypatch.setattr(mailer, "ATTACHMENT_DIR", tmp_path / "bijlagen")


def test_mail_met_afbeelding_onderaan(config, tmp_path, monkeypatch):
    (tmp_path / "uitvoerend.jpg").write_bytes(b"\xff\xd8\xff\xe0nep-jpeg")
    _use_dir(monkeypatch, tmp_path)

    msg = mailer.Message("Onderwerp", "Hallo <Alfa>\n\nGroet\n--\nAfmelden: stop\n")
    email = mailer.build(config, _recipient(), msg)

    plain = email.get_body(("plain",)).get_content()
    html = email.get_body(("html",)).get_content()
    assert "Hallo <Alfa>" in plain
    assert "Hallo &lt;Alfa&gt;" in html
    # De afbeelding staat onderaan, maar boven de afmeldregel.
    assert html.index("cid:") < html.index("Afmelden")
    jpg = [p for p in email.walk() if p.get_content_type() == "image/jpeg"]
    assert len(jpg) == 1 and jpg[0]["Content-ID"][1:-1] in html


def test_afbeelding_en_bijlagen_alleen_voor_eigen_variant(config, tmp_path, monkeypatch):
    (tmp_path / "uitvoerend.jpg").write_bytes(b"\xff\xd8nep")
    folder = tmp_path / "bijlagen" / "ontwerp"
    folder.mkdir(parents=True)
    (folder / "certificaat.pdf").write_bytes(b"%PDF-nep")
    _use_dir(monkeypatch, tmp_path)

    ontwerp = mailer.build(config, _recipient("ontwerp"), mailer.Message("O", "Tekst\n"))
    assert [a.get_filename() for a in ontwerp.iter_attachments()] == ["certificaat.pdf"]
    assert not any(p.get_content_type() == "image/jpeg" for p in ontwerp.walk())
    assert ontwerp.get_body(("plain",)).get_content() == "Tekst\n"

    uitvoerend = mailer.build(config, _recipient(), mailer.Message("O", "Tekst\n"))
    assert list(uitvoerend.iter_attachments()) == []


def test_zonder_afbeelding_gewone_tekstmail(config, tmp_path, monkeypatch):
    _use_dir(monkeypatch, tmp_path)
    email = mailer.build(config, _recipient(), mailer.Message("O", "Tekst\n"))
    assert email.get_content_type() == "text/plain"
