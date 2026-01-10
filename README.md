# Padel Notifier

Scrape 4PADEL tournaments and notify on new P100/P250 via macOS notifications (local) and email (SMTP). Optionally runs every 30 minutes on GitHub Actions.

## Local usage (macOS)
- Install deps:
```
pip install -r requirements.txt
python -m playwright install chromium
```
- Initialize state and run notifier:
```
python 4padel.py
python padel_notify.py --init
python padel_notify.py --watch --interval 15 --email
```
- Configure email in `.padel_email.json` (copy from `padel_email.example.json`).

## LaunchAgent (every 30 min)
- Plist installed at `~/Library/LaunchAgents/com.padel.notify.plist`.
- Manage:
```
launchctl unload ~/Library/LaunchAgents/com.padel.notify.plist
launchctl load   ~/Library/LaunchAgents/com.padel.notify.plist
launchctl list | grep com.padel.notify
```

## GitHub Actions (runs when your computer is off)
- Workflow file: `.github/workflows/padel_cron.yml` (runs every 30 minutes).
- Push this folder to a GitHub repo, then add repository secrets (Settings → Secrets and variables → Actions → New repository secret):
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`, `TO_EMAIL`, `USE_TLS`, `USE_SSL`.
- The workflow installs deps, builds `.padel_email.json` from secrets, runs `padel_notify.py --email` and commits `.padel_state.json` to persist seen tournaments.

### Secrets: what to put where
- Do NOT commit your real `.padel_email.json` to git. It's ignored via `.gitignore`.
- For local tests only, copy `padel_email.example.json` to `.padel_email.json` and fill with your details.
- For GitHub Actions, put your credentials as repository secrets. The workflow creates `.padel_email.json` at runtime from these secrets:
  - `SMTP_HOST`: e.g. `smtp.gmail.com`, `smtp-mail.outlook.com`, `smtp.office365.com`, or `smtp.sendgrid.net`.
  - `SMTP_PORT`: usually `587` (TLS) or `465` (SSL).
  - `SMTP_USER`: your SMTP login. For SendGrid use `apikey`.
  - `SMTP_PASSWORD`: your password or provider API key.
  - `FROM_EMAIL`: the sender address (must be verified for some providers).
  - `TO_EMAIL`: where you want to receive alerts.
  - `USE_TLS`: `true`/`false` (typically `true`).
  - `USE_SSL`: `true`/`false` (typically `false`).

Provider quick tips
- Gmail: enable 2FA, create an App Password (Google Account → Security → App passwords), then use:
  - `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `USE_TLS=true`, `USE_SSL=false`.
- Outlook.com/Hotmail: `SMTP_HOST=smtp-mail.outlook.com`, `SMTP_PORT=587`, `USE_TLS=true`.
- Microsoft 365 (Exchange Online): `SMTP_HOST=smtp.office365.com`, `SMTP_PORT=587`, `USE_TLS=true`.
- SendGrid: `SMTP_HOST=smtp.sendgrid.net`, `SMTP_PORT=587`, `SMTP_USER=apikey`, `SMTP_PASSWORD=<your_api_key>`.

## Notes
- New tournaments are computed by `current_keys - prev_keys` in `check_once()` using keys: `(club, date, heure, nom)`.
- If organisers edit tournaments (date/time/name), they may be detected as new; we can switch to a more stable identifier if we can scrape a unique URL (future enhancement).
