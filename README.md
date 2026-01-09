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
- Push this folder to a GitHub repo, then add repository secrets:
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`, `TO_EMAIL`, `USE_TLS`, `USE_SSL`.
- The workflow installs deps, builds `.padel_email.json` from secrets, runs `padel_notify.py --email` and commits `.padel_state.json` to persist seen tournaments.

## Notes
- New tournaments are computed by `current_keys - prev_keys` in `check_once()` using keys: `(club, date, heure, nom)`.
- If organisers edit tournaments (date/time/name), they may be detected as new; we can switch to a more stable identifier if we can scrape a unique URL (future enhancement).
