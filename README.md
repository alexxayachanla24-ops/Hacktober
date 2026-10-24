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

## Local AI cleanliness review

New completion submissions require a **clean** verdict from a local vision model.
The default is [Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct),
an open-weight model licensed under Apache 2.0. It runs through
[Ollama](https://ollama.com/download/windows); no hosted AI service or API key is used.
The model and Ollama are not bundled or installed by this repository.

1. Install Ollama from the official link above and start it.
2. Download the model (approximately 3.3 GB):

   ```powershell
   ollama pull qwen3-vl:4b-instruct
   ```

3. If Ollama is not already running, run `ollama serve` in another terminal.
4. Install the Python requirements, start Flask, and open a pending chore's portal.
   Upload a clear photo of the cleaned area and choose **Scan photo & submit**.

The model returns `clean`, `needs_work`, or `unclear`, along with a reason and
actionable issues. Only `clean` completes the chore and awards leaderboard points.
Other verdicts leave it pending so a new photo can be submitted. Missing models,
timeouts, invalid files, and malformed model responses do not approve completion.
Existing resolved chores remain resolved; they are not automatically rescanned.

Photos are decoded and checked, oriented, limited to 1024 pixels on the longest
edge, and re-encoded without metadata before inference. Images must be at least
64 × 64 pixels and at most 25 megapixels. The AI checks visible relevant mess;
it cannot establish hygiene, hidden work, or that a photo is current. Its opinion
can be wrong. Use a photo of the chore area rather than a face or illustration.
Successful photos are retained; rejected or failed uploads are removed. The latest
valid AI review is stored with the chore and shown on the dashboard.

Optional PowerShell configuration, set before starting Flask:

```powershell
$env:OLLAMA_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_MODEL = 'qwen3-vl:4b-instruct'
```

Only loopback HTTP addresses are accepted; proxies are bypassed. The default
inference timeout is 120 seconds. For another locally installed vision model,
set `OLLAMA_MODEL` to its Ollama name; it must support image input and structured
JSON output. See the official [Ollama image/structured-output API](https://docs.ollama.com/api/generate).

Tests use controlled model responses; they do not download weights or measure
real-model accuracy. To verify a real model, install it as above and try a clear
clean-area photo, a visibly dirty-area photo, and an unrelated image. Confirm the
returned observations match what is visible before relying on the assessment.

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
Selecting a completion photo in the roommate portal plays the supplied Fahh
reaction sound. Clearing the file selection does not play it.

## Checks

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
node --test tests/frontend.test.cjs tests/tung.test.cjs tests/leaderboard.test.cjs
```

API tests use temporary databases and uploads. Frontend tests use Node's built-in
test runner with a minimal DOM harness; no additional test packages are needed.
`create_app(config)` accepts `DATABASE`, `UPLOAD_FOLDER`, and Flask settings for
isolated app instances. Existing databases gain the walker column automatically.
