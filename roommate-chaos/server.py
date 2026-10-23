"""Chore Enforcement System 95 - local backend. Run: python server.py"""
import os, sqlite3, time, uuid
from flask import Flask, request, jsonify, send_from_directory, g, abort

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(BASE, "uploads")
DB = os.path.join(BASE, "chaos.db")
os.makedirs(UPLOADS, exist_ok=True)
EXT = {"png", "jpg", "jpeg", "gif", "webp", "mp3", "wav", "ogg", "m4a", "webm"}

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


with sqlite3.connect(DB) as c:
    c.execute("""CREATE TABLE IF NOT EXISTS chores(
        id TEXT PRIMARY KEY, chore TEXT, target TEXT, evidence TEXT, payload TEXT,
        ptype TEXT, status TEXT DEFAULT 'pending', age_photo TEXT,
        created REAL, resolved REAL)""")


def save(field):
    """Save an uploaded file and return its stored name (or None)."""
    f = request.files.get(field)
    if not f or not f.filename:
        return None, None
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in EXT:
        return None, None
    name = uuid.uuid4().hex + "." + ext
    f.save(os.path.join(UPLOADS, name))
    return name, f.mimetype


def url(name):
    return "/uploads/" + name if name else None


def row_json(r):
    return {"id": r["id"], "chore": r["chore"], "target": r["target"],
            "evidence": url(r["evidence"]), "payload": url(r["payload"]),
            "ptype": r["ptype"] or "", "status": r["status"],
            "age_photo": url(r["age_photo"]), "created": r["created"],
            "resolved": r["resolved"]}


@app.get("/")
def index():
    return send_from_directory(os.path.join(BASE, "static"), "index.html")


@app.get("/uploads/<path:name>")
def uploads(name):
    return send_from_directory(UPLOADS, name)


@app.post("/api/chores")
def create_chore():
    chore = (request.form.get("chore") or "").strip()[:300]
    target = (request.form.get("target") or "").strip()[:200]
    if not chore or not target:
        return jsonify(error="chore and target are required"), 400
    ev, _ = save("evidence")
    pl, ptype = save("payload")
    cid = uuid.uuid4().hex[:8]
    db().execute("INSERT INTO chores(id,chore,target,evidence,payload,ptype,created) VALUES(?,?,?,?,?,?,?)",
                 (cid, chore, target, ev, pl, ptype, time.time()))
    db().commit()
    return jsonify(id=cid), 201


@app.get("/api/chores")
def list_chores():
    rows = db().execute("SELECT * FROM chores ORDER BY created DESC").fetchall()
    return jsonify([row_json(r) for r in rows])


@app.get("/api/chores/<cid>")
def get_chore(cid):
    r = db().execute("SELECT * FROM chores WHERE id=?", (cid,)).fetchone()
    if not r:
        abort(404)
    return jsonify(row_json(r))


@app.post("/api/chores/<cid>/resolve")
def resolve(cid):
    if not db().execute("SELECT 1 FROM chores WHERE id=?", (cid,)).fetchone():
        abort(404)
    age, _ = save("age")
    db().execute("UPDATE chores SET status='resolved', age_photo=?, resolved=? WHERE id=?",
                 (age, time.time(), cid))
    db().commit()
    return jsonify(ok=True)


DASH = """<!DOCTYPE html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Chore Tribunal</title><style>
body{margin:0;background:#008080;font:15px Tahoma,Arial,sans-serif;padding:12px}
h1{font:900 24px 'Courier New',monospace;color:#ff0;text-shadow:2px 2px #f0f}
.c{background:#c0c0c0;border:2px solid;border-color:#fff #000 #000 #fff;margin:10px 0;padding:10px;display:flex;gap:10px;flex-wrap:wrap;color:#000}
.c img{height:90px;border:2px solid #808080}.s{font-weight:bold}.pending{color:#a00}.resolved{color:#060}
</style><h1>CHORE TRIBUNAL DASHBOARD</h1><a href="/" style="color:#fff">+ New nag</a><div id=l></div>
<script>
async function load(){const d=await (await fetch('/api/chores')).json(),l=document.getElementById('l');l.innerHTML='';
if(!d.length)l.textContent='No grievances yet. Suspiciously peaceful.';
d.forEach(c=>{const e=document.createElement('div');e.className='c';
const t=document.createElement('div');
const a=document.createElement('b');a.textContent=c.chore;t.append(a,document.createElement('br'),'Target: '+c.target,document.createElement('br'));
const s=document.createElement('span');s.className='s '+c.status;s.textContent=c.status==='resolved'?'RESOLVED (for now) '+new Date(c.resolved*1000).toLocaleString():'PENDING — still gross';t.append(s,document.createElement('br'));
const k=document.createElement('a');k.href='/?c='+c.id;k.textContent='Portal link';t.append(k);e.append(t);
[c.evidence,c.age_photo].forEach(u=>{if(u){const i=document.createElement('img');i.src=u;e.append(i)}});l.append(e)})}
load();setInterval(load,3000);
</script>"""


@app.get("/dashboard")
def dashboard():
    return DASH


if __name__ == "__main__":
    print("Chore Enforcement System 95 running at http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
