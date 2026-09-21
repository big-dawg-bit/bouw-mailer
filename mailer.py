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

    fields = {
        "bedrijfsnaam": recipient.company,
        "plaats": getattr(recipient, "city", "") or "",
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

    def __enter__(self):
        cfg = self.config
        try:
            self.smtp = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30)
            self.smtp.starttls(context=ssl.create_default_context())
            self.smtp.login(cfg.smtp_user, cfg.smtp_password)
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
        self.smtp.send_message(email)

    def __exit__(self, *exc_info):
        if self.smtp is not None:
            try:
                self.smtp.quit()
            except smtplib.SMTPException:
                pass
        return False
