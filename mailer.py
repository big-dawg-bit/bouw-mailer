"""Templates renderen en mail versturen via SMTP."""

import smtplib
import ssl
import sys
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

from config import TEMPLATE_DIR


@dataclass
class Message:
    subject: str
    body: str


def load_template(variant: str) -> str:
    path = TEMPLATE_DIR / f"{variant}.txt"
    if not path.exists():
        sys.exit(f"FOUT: template ontbreekt: {path}")
    return path.read_text(encoding="utf-8")


def render(variant: str, recipient) -> Message:
    """Eerste regel is 'Subject: ...', dan een lege regel, dan de body."""
    raw = load_template(variant)
    head, _, body = raw.partition("\n\n")
    if not head.lower().startswith("subject:"):
        sys.exit(
            f"FOUT: {variant}.txt moet beginnen met een regel 'Subject: ...', "
            f"gevolgd door een lege regel."
        )

    city = (getattr(recipient, "city", "") or "").strip()
    fields = {
        "bedrijfsnaam": recipient.company,
        "plaats": city,
        # Midden in een zin: levert " in Maastricht" of niets, zodat een lege
        # Plaats geen dubbele spatie achterlaat.
        "in_plaats": f" in {city}" if city else "",
        "categorie": recipient.category,
    }
    try:
        subject = head.split(":", 1)[1].strip().format(**fields)
        body = body.format(**fields)
    except KeyError as exc:
        sys.exit(
            f"FOUT: {variant}.txt gebruikt onbekende placeholder {exc}. "
            f"Beschikbaar: {', '.join('{' + k + '}' for k in fields)}"
        )
    except (ValueError, IndexError) as exc:
        sys.exit(
            f"FOUT: {variant}.txt bevat een losse accolade ({exc}).\n"
            f"      Wil je letterlijk {{ of }} in de tekst? Schrijf ze dubbel: "
            f"{{{{ en }}}}."
        )
    return Message(subject=subject, body=body.strip() + "\n")


def build(config, recipient, message: Message) -> EmailMessage:
    email = EmailMessage()
    email["From"] = config.from_header
    email["To"] = recipient.email
    email["Subject"] = message.subject
    email["Reply-To"] = config.reply_to
    email.set_content(message.body)
    return email


class Sender:
    """Eén SMTP-verbinding voor de hele run, in plaats van per mail opnieuw."""

    def __init__(self, config):
        self.config = config
        self.smtp = None

    def _connect(self) -> None:
        cfg = self.config
        self.smtp = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30)
        self.smtp.starttls(context=ssl.create_default_context())
        self.smtp.login(cfg.smtp_user, cfg.smtp_password)

    def __enter__(self):
        cfg = self.config
        try:
            self._connect()
        except smtplib.SMTPAuthenticationError:
            sys.exit(
                "FOUT: inloggen geweigerd door de mailserver.\n"
                "      Bij Gmail: gebruik een 16-cijferig App Password, niet je\n"
                "      gewone wachtwoord, en zet 2-staps-verificatie aan.\n"
                "      https://myaccount.google.com/apppasswords"
            )
        except (OSError, smtplib.SMTPException) as exc:
            sys.exit(f"FOUT: geen verbinding met {cfg.smtp_host}:{cfg.smtp_port} - {exc}")
        return self

    def send(self, email: EmailMessage) -> None:
        try:
            self.smtp.send_message(email)
        except smtplib.SMTPServerDisconnected:
            # Gmail verbreekt bij een lange run soms de verbinding. Eén keer
            # opnieuw verbinden en deze mail alsnog proberen; lukt dat niet,
            # dan laten we de fout door zodat de loop hem als MISLUKT logt.
            print("      verbinding verbroken, opnieuw verbinden...")
            self._connect()
            self.smtp.send_message(email)

    def __exit__(self, *exc_info):
        if self.smtp is not None:
            try:
                self.smtp.quit()
            except smtplib.SMTPException:
                pass
        return False
