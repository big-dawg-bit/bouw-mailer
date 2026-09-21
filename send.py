"""Versturen van de wervingsmails.

    python send.py                           dry-run: laat zien wat er zou gebeuren
    python send.py --send                    echt versturen
    python send.py --send --limit 3          alleen de eerste 3
    python send.py --send --variant ontwerp  alleen een segment
"""

import argparse
import csv
import sys
import time
from datetime import datetime

from config import SENT_LOG, VARIANTS, Config
from mailer import Sender, build, render
from recipients import load_recipients


def read_sent_log() -> set:
    if not SENT_LOG.exists():
        return set()
    with SENT_LOG.open(newline="", encoding="utf-8") as handle:
        return {
            row["email"].strip().lower()
            for row in csv.DictReader(handle)
            if row.get("email")
        }


def append_sent_log(recipient) -> None:
    is_new = not SENT_LOG.exists()
    with SENT_LOG.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(["timestamp", "email", "company", "variant"])
        writer.writerow(
            [
                datetime.now().isoformat(timespec="seconds"),
                recipient.email,
                recipient.company,
                recipient.variant,
            ]
        )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--send",
        action="store_true",
        help="daadwerkelijk versturen (zonder deze vlag: dry-run)",
    )
    parser.add_argument("--limit", type=int, help="stop na dit aantal mails")
    parser.add_argument(
        "--variant", choices=VARIANTS, help="alleen deze variant versturen"
    )
    parser.add_argument(
        "--resend",
        action="store_true",
        help="negeer sent_log.csv en stuur ook naar al gemailde adressen",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = Config()
    report = load_recipients(config.excel_path)

    print(f"Bestand      : {config.excel_path}")
    print(f"Regels gelezen: {report.rows_read}")
    print(f"Geen e-mail   : {report.skipped_no_email} overgeslagen")

    if report.skipped_bad_email:
        print(f"Ongeldig adres: {len(report.skipped_bad_email)} overgeslagen")
        for company, email in report.skipped_bad_email:
            print(f"   - {company}: {email}")

    if report.skipped_unknown_category:
        print(
            f"Onbekende categorie: {len(report.skipped_unknown_category)} overgeslagen"
        )
        for company, category in report.skipped_unknown_category:
            print(f"   - {company}: {category}")

    if report.merged:
        print(f"\nGedeelde adressen samengevoegd ({len(report.merged)}):")
        for line in report.merged:
            print(f"   - {line}")

    targets = report.recipients
    if args.variant:
        targets = [r for r in targets if r.variant == args.variant]

    already = set() if args.resend else read_sent_log()
    if already:
        before = len(targets)
        targets = [r for r in targets if r.email.lower() not in already]
        print(f"\nAl eerder gemaild: {before - len(targets)} overgeslagen")

    counts = {v: sum(1 for r in targets if r.variant == v) for v in VARIANTS}
    print(f"\nTe versturen: {len(targets)} mails")
    for variant, count in counts.items():
        print(f"   {variant:<14} {count}")

    if args.limit is not None:
        targets = targets[: args.limit]
        print(f"   (beperkt tot {len(targets)} door --limit)")

    if not targets:
        print("\nNiets te doen.")
        return 0

    if not args.send:
        print("\n--- DRY-RUN, er wordt niets verstuurd ---")
        print("Voorbeeld per variant:\n")
        seen = set()
        for recipient in targets:
            if recipient.variant in seen:
                continue
            seen.add(recipient.variant)
            message = render(recipient.variant, recipient)
            print(f"[{recipient.variant}] naar {recipient.email} ({recipient.company})")
            print(f"Onderwerp: {message.subject}")
            print(message.body)
            print("-" * 60)
        print("Klopt het? Draai dan:  python send.py --send --limit 1")
        return 0

    config.require_smtp()

    sent = 0
    failed = []
    with Sender(config) as sender:
        for index, recipient in enumerate(targets, start=1):
            message = render(recipient.variant, recipient)
            email = build(config, recipient, message)
            try:
                sender.send(email)
            except Exception as exc:  # één slecht adres mag de run niet slopen
                failed.append((recipient.email, str(exc)))
                print(f"[{index}/{len(targets)}] MISLUKT {recipient.email}: {exc}")
                continue

            append_sent_log(recipient)
            sent += 1
            print(
                f"[{index}/{len(targets)}] verstuurd -> {recipient.email} "
                f"({recipient.variant})"
            )
            if index < len(targets):
                time.sleep(config.send_delay)

    print(f"\nKlaar: {sent} verstuurd, {len(failed)} mislukt.")
    for email, error in failed:
        print(f"   - {email}: {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
