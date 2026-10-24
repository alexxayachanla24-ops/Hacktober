"""Chore Enforcement System 95 - local backend. Run: python server.py"""
import os
import sqlite3
import time
import uuid
import json
from contextlib import closing

from flask import Blueprint, Flask, current_app, request, jsonify, send_from_directory, g, abort
from werkzeug.exceptions import HTTPException
from cleanliness import InvalidPhoto, ReviewUnavailable, review_photo

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(BASE, "uploads")
DB = os.path.join(BASE, "chaos.db")
MEDIA_TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "webp": "image/webp", "mp3": "audio/mpeg",
    "wav": "audio/wav", "ogg": "audio/ogg", "m4a": "audio/mp4",
    "webm": "audio/webm",
}
IMAGE_EXT = {ext for ext, mime in MEDIA_TYPES.items() if mime.startswith("image/")}
CHALLENGES = {"easy": 5, "medium": 10, "boss": 15}
routes = Blueprint("chores", __name__)


def db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    with closing(sqlite3.connect(current_app.config["DATABASE"])) as c, c:
        c.execute("""CREATE TABLE IF NOT EXISTS chores(
        id TEXT PRIMARY KEY, chore TEXT, target TEXT, evidence TEXT, payload TEXT,
        ptype TEXT, status TEXT DEFAULT 'pending', age_photo TEXT,
        created REAL, resolved REAL)""")
        if "walker" not in {r[1] for r in c.execute("PRAGMA table_info(chores)")}:
            c.execute("ALTER TABLE chores ADD COLUMN walker TEXT")
        columns = {r[1] for r in c.execute("PRAGMA table_info(chores)")}
        for column, kind in (("challenge", "TEXT"), ("deadline", "REAL"), ("ai_review", "TEXT")):
            if column not in columns:
                c.execute(f"ALTER TABLE chores ADD COLUMN {column} {kind}")


def save(field, allowed=None, required=False):
    """Validate and save an upload, tracking it for cleanup on failed requests."""
    f = request.files.get(field)
    if not f or not f.filename:
        if required:
            abort(400, description=f"{field} photo is required")
        return None, None
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in (allowed if allowed is not None else MEDIA_TYPES):
        abort(400, description=f"Unsupported file type for {field}")
    if not f.stream.read(1):
        abort(400, description=f"{field} file is empty")
    f.stream.seek(0)
    name = uuid.uuid4().hex + "." + ext
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], name)
    g.setdefault("new_uploads", []).append(path)
    f.save(path)
    return name, MEDIA_TYPES[ext]


def cleanup_uploads(_):
    if not g.get("uploads_committed", False):
        for path in g.pop("new_uploads", []):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass


def url(name):
    return "/uploads/" + name if name else None


def row_json(r):
    return {"id": r["id"], "chore": r["chore"], "target": r["target"],
            "evidence": url(r["evidence"]), "payload": url(r["payload"]),
            "ptype": r["ptype"] or "", "status": r["status"],
            "age_photo": url(r["age_photo"]), "created": r["created"],
            "resolved": r["resolved"], "walker": url(r["walker"]),
            "challenge": r["challenge"], "deadline": r["deadline"],
            "ai_review": json.loads(r["ai_review"]) if r["ai_review"] else None}


@routes.get("/")
def index():
    return send_from_directory(os.path.join(BASE, "static"), "index.html")


@routes.get("/uploads/<path:name>")
def uploads(name):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], name)


@routes.post("/api/chores")
def create_chore():
    chore = (request.form.get("chore") or "").strip()[:300]
    target = (request.form.get("target") or "").strip()[:200]
    if not chore or not target:
        return jsonify(error="chore and target are required"), 400
    challenge = request.form.get("challenge") or None
    if challenge is not None and challenge not in CHALLENGES:
        return jsonify(error="Unknown challenge difficulty"), 400
    created = time.time()
    deadline = created + CHALLENGES[challenge] * 60 if challenge else None
    ev, _ = save("evidence", IMAGE_EXT)
    pl, ptype = save("payload")
    walker, _ = save("walker", {"png"})
    cid = uuid.uuid4().hex[:8]
    db().execute("INSERT INTO chores(id,chore,target,evidence,payload,ptype,walker,created,challenge,deadline) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (cid, chore, target, ev, pl, ptype, walker, created, challenge, deadline))
    db().commit()
    g.uploads_committed = True
    return jsonify(id=cid, challenge=challenge, deadline=deadline), 201


@routes.get("/api/chores")
def list_chores():
    rows = db().execute("SELECT * FROM chores ORDER BY created DESC").fetchall()
    return jsonify([row_json(r) for r in rows])


@routes.get("/api/chores/<cid>")
def get_chore(cid):
    r = db().execute("SELECT * FROM chores WHERE id=?", (cid,)).fetchone()
    if not r:
        abort(404)
    return jsonify(row_json(r))


@routes.get("/api/leaderboard")
def leaderboard_data():
    now = time.time()
    roommates = {}
    for row in db().execute("SELECT target,status,created,resolved,deadline FROM chores ORDER BY created,id"):
        target = (row["target"] or "").strip()
        if not target:
            continue
        member = roommates.setdefault(target.casefold(), {
            "target": target, "completed": 0, "pending": 0, "on_time": 0,
            "overdue": 0, "durations": [],
        })
        if row["status"] == "resolved":
            member["completed"] += 1
            if row["resolved"] is not None and row["created"] is not None and row["resolved"] >= row["created"]:
                member["durations"].append(row["resolved"] - row["created"])
            if row["deadline"] is not None and row["resolved"] is not None and row["resolved"] <= row["deadline"]:
                member["on_time"] += 1
        else:
            member["pending"] += 1
            if row["deadline"] is not None and row["deadline"] < now:
                member["overdue"] += 1
    entries = []
    for member in roommates.values():
        durations = member.pop("durations")
        member["points"] = member["completed"] * 10 + member["on_time"] * 5
        member["fastest_seconds"] = min(durations) if durations else None
        member["average_seconds"] = sum(durations) / len(durations) if durations else None
        entries.append(member)
    entries.sort(key=lambda member: (
        -member["points"], -member["completed"],
        member["average_seconds"] if member["average_seconds"] is not None else float("inf"),
        member["target"].casefold(),
    ))
    for rank, member in enumerate(entries, 1):
        member["rank"] = rank
    return jsonify(roommates=entries, updated_at=now, totals={
        "roommates": len(entries),
        "completed": sum(member["completed"] for member in entries),
        "pending": sum(member["pending"] for member in entries),
    })


@routes.get("/leaderboard")
def leaderboard():
    return send_from_directory(os.path.join(BASE, "static"), "leaderboard.html")


@routes.post("/api/chores/<cid>/resolve")
def resolve(cid):
    row = db().execute("SELECT status,chore,ai_review FROM chores WHERE id=?", (cid,)).fetchone()
    if not row:
        abort(404)
    if row["status"] == "resolved":
        return jsonify(ok=True, review=json.loads(row["ai_review"]) if row["ai_review"] else None)
    age, _ = save("age", IMAGE_EXT, required=True)
    try:
        review = review_photo(os.path.join(current_app.config["UPLOAD_FOLDER"], age), row["chore"],
                              base_url=current_app.config["OLLAMA_URL"],
                              model=current_app.config["OLLAMA_MODEL"],
                              timeout=current_app.config["OLLAMA_TIMEOUT"])
    except InvalidPhoto as error:
        return jsonify(error=str(error)), 400
    except ReviewUnavailable as error:
        return jsonify(error=str(error)), 503
    review["reviewed_at"] = time.time()
    serialized = json.dumps(review)
    if review["verdict"] != "clean":
        db().execute("UPDATE chores SET ai_review=? WHERE id=? AND status='pending'", (serialized, cid))
        db().commit()
        return jsonify(error="The photo needs another look. Check the AI feedback and upload a clearer or cleaner result.", review=review), 422
    updated = db().execute("UPDATE chores SET status='resolved', age_photo=?, resolved=?, ai_review=? WHERE id=? AND status='pending'",
                 (age, time.time(), serialized, cid))
    db().commit()
    g.uploads_committed = updated.rowcount == 1
    return jsonify(ok=True, review=review)


DASH = """<!DOCTYPE html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Chore Tribunal</title><style>
body{margin:0;background:#008080;font:15px Tahoma,Arial,sans-serif;padding:12px}
h1{font:900 24px 'Courier New',monospace;color:#ff0;text-shadow:2px 2px #f0f}
.c{background:#c0c0c0;border:2px solid;border-color:#fff #000 #000 #fff;margin:10px 0;padding:10px;display:flex;gap:10px;flex-wrap:wrap;color:#000}
.c img{height:90px;border:2px solid #808080}.s{font-weight:bold}.pending{color:#a00}.resolved{color:#060}
</style><h1>CHORE TRIBUNAL DASHBOARD</h1><a href="/" style="color:#fff">+ New nag</a> · <a href="/leaderboard" style="color:#fff">🏆 Roommate leaderboard</a><div id=l></div>
<script>
async function load(){const d=await (await fetch('/api/chores')).json(),l=document.getElementById('l');l.innerHTML='';
if(!d.length)l.textContent='No grievances yet. Suspiciously peaceful.';
d.forEach(c=>{const e=document.createElement('div');e.className='c';
const t=document.createElement('div');
const a=document.createElement('b');a.textContent=c.chore;t.append(a,document.createElement('br'),'Target: '+c.target,document.createElement('br'));
const s=document.createElement('span');s.className='s '+c.status;s.textContent=c.status==='resolved'?'RESOLVED (for now) '+new Date(c.resolved*1000).toLocaleString():'PENDING — still gross';t.append(s,document.createElement('br'));
if(c.deadline){const timer=document.createElement('span');const left=Math.max(0,Math.ceil(c.deadline-Date.now()/1000));timer.textContent=c.status==='resolved'?'Roulette challenge completed':left?`Roulette: ${Math.floor(left/60)}:${String(left%60).padStart(2,'0')} remaining`:'Roulette: time is up — submission still open';t.append(timer,document.createElement('br'));}
if(c.ai_review){const review=document.createElement('p');review.textContent='AI cleanliness: '+c.ai_review.verdict+' — '+c.ai_review.reason;t.append(review);}
const k=document.createElement('a');k.href='/?c='+c.id;k.textContent='Portal link';t.append(k);e.append(t);
[c.evidence,c.age_photo].forEach(u=>{if(u){const i=document.createElement('img');i.src=u;e.append(i)}});l.append(e)})}
load();setInterval(load,3000);
</script>"""


@routes.get("/dashboard")
def dashboard():
    return DASH


def create_app(config=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.from_mapping(
        DATABASE=DB, UPLOAD_FOLDER=UPLOADS, MAX_CONTENT_LENGTH=50 * 1024 * 1024,
        OLLAMA_URL=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"),
        OLLAMA_MODEL=os.environ.get("OLLAMA_MODEL", "qwen3-vl:4b-instruct"),
        OLLAMA_TIMEOUT=120,
    )
    if config:
        app.config.update(config)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.register_blueprint(routes)
    app.teardown_appcontext(close_db)
    app.teardown_appcontext(cleanup_uploads)

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/"):
            response = error.get_response()
            response.data = app.json.dumps({"error": error.description})
            response.content_type = "application/json"
            return response
        return error

    with app.app_context():
        init_db()
    return app


app = create_app()


if __name__ == "__main__":
    print("Chore Enforcement System 95 running at http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
