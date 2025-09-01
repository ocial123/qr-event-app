import os
import sqlite3
import uuid
import io
from datetime import datetime
from flask import Flask, g, render_template, request, redirect, url_for, send_file, session, jsonify, flash

import qrcode

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_change_me")

DATABASE = os.path.join(os.path.dirname(__file__), "data.db")
ADMIN_USERS = os.getenv("ADMIN_USERS", "admin:password").split(",")  # format user:pass,user2:pass2

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE,
        meta TEXT,
        created_at TIMESTAMP,
        used_at TIMESTAMP,
        used_by TEXT
    )""")
    db.commit()

@app.before_request
def setup():
    if not hasattr(app, "_db_initialized"):
        init_db()
        app._db_initialized = True


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def is_admin_credentials(username, password):
    for cred in ADMIN_USERS:
        if ':' in cred:
            u,p = cred.split(':',1)
            if u == username and p == password:
                return True
    return False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate", methods=["GET","POST"])
def generate():
    db = get_db()
    if request.method == "POST":
        count = int(request.form.get("count", "1"))
        meta = request.form.get("meta","")
        created = []
        for _ in range(count):
            token = str(uuid.uuid4())
            db.execute("INSERT INTO tokens (token, meta, created_at) VALUES (?, ?, ?)",
                       (token, meta, datetime.utcnow()))
            created.append(token)
        db.commit()
        return render_template("generate.html", tokens=created)
    return render_template("generate.html", tokens=None)

@app.route("/qrcode/<token>")
def qrcode_img(token):
    # serve PNG image of the token's URL
    host = request.host_url.rstrip("/")
    token_url = f"{host}/s/{token}"
    img = qrcode.make(token_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name=f"{token}.png", as_attachment=False)

@app.route("/s/<token>")
def public_scan(token):
    # This is the page that opens when a normal QR scanner opens the token URL.
    # Per requirements, it should do nothing important for non-admins.
    db = get_db()
    row = db.execute("SELECT * FROM tokens WHERE token = ?", (token,)).fetchone()
    exists = row is not None
    used = bool(row["used_at"]) if row else False
    # show a simple RAVE page or minimal info — do NOT change DB state
    return render_template("public_scan.html", exists=exists, used=used)

# --- Admin routes ---
@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")
        if is_admin_credentials(user, pwd):
            session["admin_user"] = user
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("admin_login.html")

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("admin_user"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapped

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    stats = db.execute("SELECT COUNT(*) as total, SUM(CASE WHEN used_at IS NOT NULL THEN 1 ELSE 0 END) as used FROM tokens").fetchone()
    tokens = db.execute("SELECT * FROM tokens ORDER BY created_at DESC LIMIT 200").fetchall()
    return render_template("admin_dashboard.html", user=session.get("admin_user"), stats=stats, tokens=tokens)

@app.route("/admin/validate", methods=["POST"])
@admin_required
def admin_validate():
    data = request.get_json() or {}
    token = data.get("token")
    admin = session.get("admin_user")
    if not token:
        return jsonify({"ok": False, "msg": "no token"}), 400
    db = get_db()
    row = db.execute("SELECT * FROM tokens WHERE token = ?", (token,)).fetchone()
    if not row:
        return jsonify({"ok": False, "msg": "token not found"}), 404
    if row["used_at"]:
        return jsonify({"ok": False, "msg": "already used", "used_at": row["used_at"], "used_by": row["used_by"]})
    db.execute("UPDATE tokens SET used_at = ?, used_by = ? WHERE token = ?", (datetime.utcnow(), admin, token))
    db.commit()
    return jsonify({"ok": True, "msg": "validated", "token": token})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)
