# Chore Enforcement System 95

A local Flask app for creating chore complaints, sharing a roommate portal,
and tracking submissions on a retro dashboard. Notifications in the app are
simulated; the send link opens your own messaging or mail app.

## Chore Roulette

Use **Spin my chore** in the setup wizard to pick a surprise task: Easy gives
5 minutes, Medium gives 10, and Boss battle gives 15. Spinning again avoids
repeating the same task immediately. Edit the selected task to turn it back into
a regular complaint without a timer.

The countdown starts when the complaint is saved. Its deadline is stored in the
database and shown in the outbox, shared roommate portal, and dashboard.
Reloading the portal does not reset it. Overdue challenges still accept submissions.

## Tung Tung chase

In the roommate portal, Tung Tung follows your cursor. Getting caught freezes the
page for 0.9 seconds and shakes it, with a short grace period before another catch.
Press Escape to break free early. Grab and drag him, then release to throw him;
he bounces off the window edges before chasing again. Hit him 20 times within a
rolling five-second window to trigger a six-second dance. The counter shows your
progress. Keyboard users can focus him and tap Enter or Space to score hits.
Reduced-motion preferences disable the shake and dance motion.

## Roommate leaderboard

Open `/leaderboard` from the setup page or dashboard. Existing complaints count
automatically: each completed chore earns 10 points, with 5 extra for finishing
a Roulette challenge on time. Standings show completed, pending, overdue, and
on-time chores plus fastest and average completion times. Ties use completed
chores, average completion time, then alphabetical order. Matching targets are
grouped without case or surrounding spaces; use a consistent phone, email, or
name for each roommate. The board refreshes every 10 seconds and keeps previously
loaded scores visible if a refresh fails. New scores appear when a chore is resolved.

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
node --test tests/frontend.test.cjs tests/tung.test.cjs tests/leaderboard.test.cjs
```

API tests use temporary databases and uploads. Frontend tests use Node's built-in
test runner with a minimal DOM harness; no additional test packages are needed.
`create_app(config)` accepts `DATABASE`, `UPLOAD_FOLDER`, and Flask settings for
isolated app instances. Existing databases gain the walker column automatically.
