# BulkMailer V1.0.0

A local-first bulk email sender for Gmail. Runs entirely on your machine — no cloud, no subscriptions, no data leaves your device.

---

## Features

- **Campaign management** — create campaigns with a subject and HTML body
- **Template variables** — use `{{name}}`, `{{company}}` style placeholders per recipient; values in the HTML body may include markup such as links or formatting
- **CSV import** — paste or upload a CSV of recipients with custom columns
- **Attachments** — fixed files or per-recipient templated filenames
- **Preview** — render and review emails before sending
- **Send controls** — start, pause, and resume campaigns; daily cap protection
- **Test send** — send a test email to yourself before going live
- **Secure by default** — token-authenticated, localhost-only API

---

## Requirements

- **Python 3.10+** — [python.org/downloads](https://www.python.org/downloads/) (`pip` is included)
- A Gmail account with an [App Password](https://myaccount.google.com/apppasswords) enabled

> Gmail requires 2-Step Verification to be active before App Passwords can be created.

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/gh-prince-laxamana/email-bulk-sender.git
cd email-bulk-sender
```

### 2. Run the app

**Windows:**

```
run.bat
```

**macOS / Linux:**

```bash
python run.py
```

The first launch will automatically:

- Create a `.venv/` virtual environment
- Install dependencies from `requirements.txt`
- Open the app in your browser at `http://127.0.0.1:8000`

### 3. Configure your Gmail credentials

In the app, go to **Settings** and enter:

- Your Gmail address
- Your [Gmail App Password](https://myaccount.google.com/apppasswords) (not your account password)

Credentials are stored in your OS keyring (Windows Credential Manager, macOS Keychain, or a local `secrets.json` fallback). They are **never** transmitted anywhere.

---

## How It Works

### HTML body variables

Recipient values are substituted into the HTML body as provided. This means a CSV
column or manually entered value can contain markup, for example:

```csv
email,Name,Promo
alice@example.com,Alice,"<a href=""https://example.com"" target=""_blank"">View your offer</a>"
```

Use `{{Promo}}` in the HTML body. Subject values remain plain text, while the
email's plain-text alternative is generated from the rendered HTML.

```
run.py
  └── starts uvicorn (localhost:8000)
        ├── FastAPI backend  (backend/)
        │     ├── SQLite database  (data/app.db)
        │     └── Gmail SMTP via App Password
        └── Vite frontend    (frontend/dist/)
```

- **Backend:** Python + FastAPI, SQLite, no external DB
- **Frontend:** Pre-built static files served by the backend
- **Security:** Per-launch random token, host-restricted to `127.0.0.1`/`localhost`, all secrets stored in OS keyring

---

## Project Structure

```
email-bulk-sender/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── mail_core/    # Email builder & campaign runner
│   │   ├── providers/    # Gmail SMTP provider
│   │   ├── services/     # Business logic
│   │   └── storage/      # SQLite repo & migrations
│   └── tests/            # pytest test suite
├── frontend/
│   └── dist/             # Pre-built frontend (served by backend)
├── run.py                # Entry point (auto-venv, auto-migrate, launch)
├── run.bat               # Windows launcher shortcut
└── requirements.txt
```

---

## Data & Privacy

See [PRIVACY.md](PRIVACY.md).

---

## License

MIT — use freely.
