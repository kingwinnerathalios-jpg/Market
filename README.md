# Kleine Manufaktur – Handmade E-commerce

Ein kleines Flask-Shop-Projekt mit Produktübersicht, Produktseiten, Warenkorb, SQLite und PayPal Checkout (Sandbox).

## Voraussetzungen

- Python 3.10 oder neuer
- Internetverbindung für PayPal Checkout und die Produktbilder
- PayPal Developer Sandbox Zugangsdaten zum Testen

## Installation

```bash
# 1. Projektordner öffnen
cd handmade_market

# 2. Virtuelle Umgebung erstellen
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1

# macOS / Linux:
source .venv/bin/activate

# 3. Pakete installieren
pip install -r requirements.txt

# 4. Umgebungsdatei anlegen
# Windows:
copy .env.example .env
# macOS / Linux:
cp .env.example .env
```

Öffne `.env` und trage einen langen zufälligen `FLASK_SECRET_KEY` sowie deine PayPal-Sandbox-Zugangsdaten ein.

## PayPal Sandbox einrichten

1. Öffne https://developer.paypal.com/
2. Melde dich an und öffne Apps & Credentials.
3. Wähle **Sandbox** und erstelle eine REST API App.
4. Kopiere Client ID und Secret in `.env`.
5. Lass `PAYPAL_MODE=sandbox`, bis du den gesamten Ablauf getestet hast.
6. Starte den Shop neu. Der PayPal-Button erscheint im Warenkorb.

Für Testzahlungen kannst du im PayPal Developer Dashboard Sandbox Buyer Accounts verwenden. Nutze keine echten Zahlungsdaten zum Testen.

## Starten

```bash
python app.py
```

Öffne anschließend http://127.0.0.1:5000

Beim ersten Start werden Beispieldaten angelegt. Die Datenbank `market.db` wird automatisch erstellt.

## Projektstruktur

```text
handmade_market/
├── app.py
├── requirements.txt
├── .env.example
├── README.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── product.html
│   ├── cart.html
│   └── success.html
└── static/
    └── style.css
```

## Funktionen

- Produktkatalog mit Bildern, Kategorien, Preisen und Lagerbestand
- Detailseite für jedes Produkt
- Session-basierter Warenkorb
- Mengen ändern und Artikel entfernen (Menge auf 0 setzen)
- Serverseitige Preisberechnung
- PayPal Orders API: Bestellung erstellen und Zahlung serverseitig bestätigen
- Lagerbestand wird nach bestätigter Zahlung reduziert
- SQLite-Datenbank mit SQLAlchemy

## Eigene Produkte hinzufügen

Die Beispieldaten werden beim ersten Start in `seed_products()` in `app.py` angelegt. Du kannst die Beispieldatensätze ändern oder neue Produkte ergänzen. Preise werden in Cent gespeichert, zum Beispiel `2490` für 24,90 €.

## Wichtige Hinweise vor echtem Einsatz

Dieses Projekt ist ein Lern- und Entwicklungsstarter, kein fertiger Shop für echte Verkäufe.

Vor einem öffentlichen Start ergänzen bzw. prüfen:
- Rechtstexte für deinen Standort: Impressum, Datenschutz, Widerruf, AGB und Versand-/Rückgabeinformationen
- Steuer-, Rechnungs- und Versandabläufe
- PayPal Webhooks zur zuverlässigen Zahlungsstatusprüfung und Behandlung doppelter Events
- CSRF-Schutz für Formulare und Rate-Limiting für Zahlungsendpunkte
- Idempotenz und persistente Bestellungen statt reinem Session-Ablauf
- Produktionsserver (z. B. Gunicorn), HTTPS, sichere Secret-Verwaltung und Backups
- Bildrechte und korrekte Produktbeschreibungen
- Tests, Monitoring und Fehlerprotokollierung

**Sicherheit:** Niemals PayPal Secret, `.env` oder andere Zugangsdaten in Git hochladen. Der Browser erhält nur die Client ID, niemals das Secret. Der Server berechnet Preise selbst. `debug` bleibt in Produktion ausgeschaltet.

## API-Routen

- `GET /` – Produktübersicht
- `GET /product/<id>` – Produktdetail
- `POST /cart/add/<id>` – Artikel hinzufügen
- `GET /cart` – Warenkorb
- `POST /cart/update` – Mengen ändern
- `POST /api/paypal/create-order` – PayPal-Bestellung serverseitig anlegen
- `POST /api/paypal/capture-order` – PayPal-Zahlung serverseitig bestätigen
- `GET /health` – einfacher Statuscheck
