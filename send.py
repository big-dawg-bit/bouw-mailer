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

from config import VARIANTS, Config
from mailer import Sender, build, load_template, render
from recipients import load_recipients


def read_sent_log(config) -> set:
    if not config.sent_log.exists():
        return set()
    with config.sent_log.open(newline="", encoding="utf-8") as handle:
        return {
            row["email"].strip().lower()
            for row in csv.DictReader(handle)
            if row.get("email")
        }


def append_sent_log(config, recipient) -> None:
    is_new = not config.sent_log.exists()
    with config.sent_log.open("a", newline="", encoding="utf-8") as handle:
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


def parse_args(argv=None):
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
    return parser.parse_args(argv)


def main(argv=None, sender_factory=Sender) -> int:
    args = parse_args(argv)
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

    already = set() if args.resend else read_sent_log(config)
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

        print("\nVolledige lijst (adres -> bedrijf [variant]):\n")
        for recipient in targets:
            regel = f"   {recipient.email} -> {recipient.company} [{recipient.variant}]"
            if recipient.also:
                regel += f"  (+ ook {', '.join(recipient.also)})"
            print(regel)

        print("\nKlopt het? Draai dan:  python send.py --send --limit 1")
        return 0

    config.require_smtp()

    # Geen mail de deur uit zolang er nog TODO's in de teksten staan.
    onaf = [
        f"templates/{variant}.txt"
        for variant in sorted({r.variant for r in targets})
        if "TODO" in load_template(variant)
    ]
    if onaf:
        sys.exit(
            "FOUT: deze teksten zijn nog niet af (er staat nog TODO in):\n"
            + "\n".join(f"      - {naam}" for naam in onaf)
            + "\n      Schrijf ze eerst af. Controleren kan met: python send.py"
        )

    sent = 0
    failed = []
    with sender_factory(config) as sender:
        for index, recipient in enumerate(targets, start=1):
            try:
                # Ook renderen en opbouwen binnen de try: een bedrijfsnaam met
                # een regeleinde laat de Subject-header struikelen, en dat mag
                # de rest van de run niet meeslepen.
                message = render(recipient.variant, recipient)
                email = build(config, recipient, message)
                sender.send(email)
            except Exception as exc:  # één slechte rij mag de run niet slopen
                failed.append((recipient.email, str(exc)))
                print(f"[{index}/{len(targets)}] MISLUKT {recipient.email}: {exc}")
                continue

            append_sent_log(config, recipient)
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
