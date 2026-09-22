# bouw-mailer

Stuurt een gerichte mail naar bouwbedrijven uit een Excel-bestand. Elk bedrijf
krijgt één van drie teksten, gekozen op basis van de kolom `Categorie`.

Geen wachtwoorden in de code, geen adressenbestand in git.

## Installeren

```bash
git clone <deze repo>
cd bouw-mailer

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

## Instellen

**1. Gmail App Password aanmaken.** Je gewone wachtwoord werkt niet voor SMTP.

- Zet 2-staps-verificatie aan op je Google-account.
- Ga naar https://myaccount.google.com/apppasswords
- Maak een wachtwoord aan en kopieer de 16 tekens.

**2. `.env` invullen.**

```bash
cp .env.example .env
```

Open `.env` en vul `SMTP_USER`, `SMTP_PASSWORD`, `FROM_NAME` en `REPLY_TO` in.
`.env` staat in `.gitignore` en komt dus nooit in git terecht.

**3. Het Excel-bestand neerzetten** in `data/`:

```
data/emailaddressen-bouwbedrijven.xlsx
```

Ook `data/` is gitignored. Het bestand bevat bedrijfsnamen, telefoonnummers,
KvK-nummers en werkadressen van met naam genoemde personen. Dat is persoons-
gegevens; die horen niet in een publieke repo, los van de wachtwoordvraag.

**4. De drie teksten schrijven.** In `templates/` staan drie bestanden met
`TODO`-markeringen. Vervang die door je eigen tekst voordat je verstuurt.

Formaat: eerste regel `Subject: ...`, dan een lege regel, dan de body.

Beschikbare placeholders:

| Placeholder | Levert | Gebruik |
|---|---|---|
| `{bedrijfsnaam}` | `Smeets Bouw BV` | overal |
| `{categorie}` | `aannemer` | overal |
| `{plaats}` | `Maastricht`, of leeg | als de plaats los staat |
| `{in_plaats}` | ` in Maastricht`, of niets | **midden in een zin** |

Niet elk bedrijf heeft een plaats in het bestand. Gebruik daarom `{in_plaats}`
zodra de plaats middenin een zin staat: bij een leeg veld valt het woord "in"
mee weg, in plaats van dat je "...juist Bouwbedrijf X in  aanschrijft" verstuurt.

Wil je letterlijk een accolade in de tekst? Schrijf hem dubbel: `{{` en `}}`.

## Gebruiken

```bash
python send.py                           # dry-run, verstuurt niets
python send.py --send --limit 1          # eerst één testmail
python send.py --send                    # de hele lijst
python send.py --send --variant ontwerp  # alleen één segment
```

Een dry-run is de standaard. Zonder `--send` wordt er geen verbinding met de
mailserver gemaakt en gaat er niets de deur uit.

De dry-run toont eerst één voorbeeldmail per variant, en daarna de volledige
koppeling van adres aan bedrijf:

```
Volledige lijst (adres -> bedrijf [variant]):

   info@voorbeeld.nl -> Voorbeeld Vastgoed BV [opdrachtgever]
   info@tweede.nl -> Tweede Ontwikkeling BV [opdrachtgever]  (+ ook Tweede Beheer B.V.)
```

Loop die lijst na voordat je verstuurt: hier zie je of elk adres aan het juiste
bedrijf en de juiste tekst hangt. `(+ ook ...)` betekent dat meer bedrijven dat
adres delen; die krijgen samen één mail, op naam van het bedrijf dat ervoor staat.

**Onafgemaakte teksten worden geweigerd.** Staat er nog `TODO` in een template
die verstuurd zou worden, dan stopt `--send` met een foutmelding voordat er ook
maar één mail uitgaat. De dry-run blijft wel gewoon werken, zodat je tussendoor
kunt controleren.

## Hoe de indeling werkt

| Variant | Categorieën |
|---|---|
| `uitvoerend` | aannemer |
| `ontwerp` | architect, ingenieursbureau |
| `opdrachtgever` | projectontwikkelaar, projectontwikkelaar/belegger, woningcorporatie |

Aanpassen doe je in `CATEGORY_VARIANTS` in `config.py`.

Er wordt alleen gemaild naar de kolom **`Algemeen e-mail`** - dus naar
`info@`-achtige adressen, niet naar de persoonlijke adressen in de kolommen
Directie / Bouw&projecten / Duurzaamheid.

**Gedeelde adressen.** Meerdere bedrijven delen soms één adres (`info@voorbeeld.nl`
staat vier keer in het bestand). Die worden samengevoegd tot één mail. Valt zo'n
adres in twee verschillende varianten, dan wint de hoogste uit `VARIANT_PRIORITY`:
`opdrachtgever` > `ontwerp` > `uitvoerend`. Het winnende bedrijf levert ook de
naam, plaats en categorie die in de mail komen te staan; de andere namen worden
er in de dry-run achter getoond. Elke samenvoeging wordt gemeld.

## sent_log.csv

Na elke geslaagde mail wordt het adres weggeschreven naar `sent_log.csv`. Bij een
volgende run worden die adressen overgeslagen, dus een afgebroken run kun je
gewoon opnieuw starten zonder dubbel te mailen. Met `--resend` negeer je het log.

Dit bestand is gitignored - het is een lijst van wie je benaderd hebt.

## Voor je verstuurt

- Er zit standaard 8 seconden tussen twee mails (`SEND_DELAY_SECONDS`). Gmail
  staat ongeveer 500 mails per dag toe; in één keer leegknallen is wat spam-
  filters laat aanslaan.
- Elke template eindigt met een afmeldregel. Laat die staan: zakelijke koude
  e-mail in Nederland moet een opt-out bieden.
- Mail alleen adressen die het bedrijf zelf gepubliceerd heeft. Het bronbestand
  is op die regel samengesteld (zie het werkblad `Toelichting`).
