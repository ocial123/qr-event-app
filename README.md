# QR Event Validator (minimal)

This is a minimal Flask web app that:
- Generates random token-based QR codes (token encoded URL)
- Stores tokens in a SQLite DB
- Allows up to N admin users (configured via environment variable) to log in and validate tokens by scanning
- Public scans (anyone scanning the QR) see a small "RAVE" page and do NOT change DB state

## Quick local run
1. Create a virtualenv and install:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Export env vars:
   ```bash
   export FLASK_SECRET_KEY="change_me"
   export ADMIN_USERS="alice:pass1,bob:pass2,charlie:pass3"
   ```
3. Start:
   ```bash
   python app.py
   ```
4. Visit `http://localhost:5000/`

## Deploy to Render (example)
- Create a new Web Service
- Connect to your Git repo or drag & drop this project
- Set Environment variables in Render dashboard:
  - `FLASK_SECRET_KEY` - random string
  - `ADMIN_USERS` - comma separated user:password pairs (exactly 3 admins recommended)
- Deploy; Render uses the `Procfile` to run gunicorn.

## How it works (short)
- Generator creates tokens and stores in `data.db`
- `/qrcode/<token>` returns a PNG of `https://yourdomain/s/<token>`
- Admins log into `/admin/login` and use `/admin/dashboard` which has a camera-based scanner that hits `/admin/validate`
- Public scanners open `/s/<token>` which shows "RAVE" (no DB writes)
