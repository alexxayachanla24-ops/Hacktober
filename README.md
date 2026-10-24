# Chore Enforcement System 95

A local Flask app for creating chore complaints, sharing a roommate portal,
and tracking submissions on a retro dashboard. Notifications in the app are
simulated; the send link opens your own messaging or mail app.

## Run

Use Python 3.10 or newer. From this directory on Windows:

```powershell
py -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe server.py
```

Open http://localhost:5000. The dashboard is at http://localhost:5000/dashboard.
The server binds to this computer only. SQLite data lives in `chaos.db`, and
uploaded media lives in `uploads/`. Back up both together to preserve complaints
and their attachments. The app has no authentication; keep it on a trusted device.

The root `server.py` and `static/index.html` are the active application. The
nested `roommate-chaos/` folder and standalone HTML files are legacy copies.
`static/index (2).html`, when present, is an older local backup and is ignored by
Git. It is not served by the application; make frontend changes in `static/index.html`.

## Uploads

Evidence and completion photos support PNG, JPEG, GIF, and WebP. Payloads also
support MP3, WAV, OGG, M4A, and WebM audio. Custom walkers must be PNG files.
The total request limit is 50 MiB. Unsupported and empty files return an error.
File types are selected by extension; uploaded content is not decoded or scanned.

## Checks

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
node --test tests/frontend.test.cjs
```

API tests use temporary databases and uploads. Frontend tests use Node's built-in
test runner with a minimal DOM harness; no additional test packages are needed.
`create_app(config)` accepts `DATABASE`, `UPLOAD_FOLDER`, and Flask settings for
isolated app instances. Existing databases gain the walker column automatically.
