# Privacy & Data Policy

**BulkMailer** is a local application. This document explains exactly what data it touches, where it is stored, and what is never collected.

---

## What BulkMailer collects

**Nothing.** BulkMailer has no telemetry, no analytics, no crash reporting, and no network connection other than sending emails through Gmail's SMTP servers on your explicit request.

---

## Where your data is stored

All data is stored **only on your machine**, in the `data/` directory created next to the app:

| Data                                | Location                          | Notes                          |
| ----------------------------------- | --------------------------------- | ------------------------------ |
| Campaigns, recipients, send history | `data/app.db` (SQLite)            | Local file, never uploaded     |
| Gmail address                       | OS keyring or `data/secrets.json` | Encrypted by OS where possible |
| Gmail App Password                  | OS keyring or `data/secrets.json` | Encrypted by OS where possible |

On Windows, credentials are stored in **Windows Credential Manager**.  
On macOS, credentials are stored in the **macOS Keychain**.  
On Linux without a keyring, credentials fall back to `data/secrets.json` (owner-read-only permissions).

---

## What is transmitted and to whom

The **only** outbound network traffic BulkMailer makes is:

- **Gmail SMTP (`smtp.gmail.com:587`)** — to deliver emails you explicitly send. This uses your own Gmail App Password and is subject to [Google's Privacy Policy](https://policies.google.com/privacy).

No data is sent to the BulkMailer author, GitHub, or any third party.

---

## Recipient data

Your recipient lists (email addresses, template values) are stored locally in `data/app.db`. You are responsible for:

- Obtaining appropriate consent from your recipients before emailing them
- Complying with applicable laws and regulations in your jurisdiction
- Keeping your recipient data safe on your own machine

---

## Security

- The API only accepts connections from `localhost` / `127.0.0.1`
- A cryptographically random token (256-bit) is generated at each launch and required for all API calls
- The token is passed via URL fragment (`#token=...`) and is never sent to any server
- All SQL queries use parameterized statements — no SQL injection is possible

---

## Open source

BulkMailer is open source. You can inspect every line of code that runs on your machine in this repository.

---

## Contact

If you have questions or concerns, open an issue on GitHub.
