from flask import Flask, jsonify, request, send_file, session, redirect, url_for
from admin_config import ADMIN_USERNAME, ADMIN_PASSWORD
from markupsafe import escape
import os
import re
import time
import uuid
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from datetime import datetime
from pathlib import Path
from functools import wraps
from auth_db import (
    get_connection,
    init_db,
    create_user,
    authenticate_user,
    update_last_login,
    mark_question_complete,
    get_completed_questions,
    get_certificate,
    create_certificate,
    get_certificate_by_id
)

app = Flask(__name__)

SECRET_KEY = os.environ.get("FLOODGATE_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("FLOODGATE_SECRET_KEY environment variable is required.")

app.secret_key = SECRET_KEY

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLOODGATE_COOKIE_SECURE", "0") == "1",
)

init_db()

BASE_DIR = Path(__file__).resolve().parent


# --------------------------------------------------
# Authentication
# --------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def valid_password(password):
    if len(password) < 12:
        return False

    if not re.search(r"[A-Z]", password):
        return False

    if not re.search(r"[a-z]", password):
        return False

    if not re.search(r"[0-9]", password):
        return False

    if not re.search(r"[^A-Za-z0-9]", password):
        return False

    return True


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password or not confirm_password:
            return "All fields are required.", 400

        if password != confirm_password:
            return "Passwords do not match.", 400

        if not valid_password(password):
            return (
                "Password must be at least 12 characters and contain "
                "uppercase, lowercase, number, and special character."
            ), 400

        user_id = create_user(username, email, password)

        if user_id is None:
            return "Username or email already exists.", 409

        session.clear()
        session["user_id"] = user_id
        session["username"] = username

        return redirect(url_for("dashboard"))

    return send_file(BASE_DIR / "register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = authenticate_user(username, password)

        if user is None:
            return "Invalid username or password.", 401

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]

        update_last_login(user["id"])

        return redirect(url_for("dashboard"))

    return send_file(BASE_DIR / "login.html")


@app.route("/me")
@login_required
def me():
    return jsonify({
        "username": session.get("username")
    })


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------
# FloodGate configuration
# --------------------------------------------------

WINDOW = 10
LIMIT = 5

clients = {}
logs = []

total_requests = 0
allowed_requests = 0
blocked_requests = 0
start_time = time.time()

# Server-side task completion state
completed_questions = set()
completed_task_ids = set()


# --------------------------------------------------
# Logging
# --------------------------------------------------

def add_log(status, ip):
    logs.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "ip": ip,
        "status": status
    })


# --------------------------------------------------
# Rate limiter
# IMPORTANT:
# Only the actual lab target "/" is rate-limited.
# Learner interface and answer checking are separate.
# --------------------------------------------------

@app.before_request
def security_monitor():
    global total_requests, allowed_requests, blocked_requests

    # Only monitor the simulated target.
    if request.path != "/":
        return

    total_requests += 1

    ip = request.remote_addr or "unknown"
    now = time.time()

    timestamps = clients.get(ip, [])

    timestamps = [
        timestamp
        for timestamp in timestamps
        if now - timestamp < WINDOW
    ]

    if len(timestamps) >= LIMIT:
        blocked_requests += 1
        add_log("BLOCKED", ip)

        return jsonify({
            "status": "blocked",
            "message": "Too many requests"
        }), 429

    timestamps.append(now)
    clients[ip] = timestamps

    allowed_requests += 1
    add_log("ALLOWED", ip)


# --------------------------------------------------
# Target
# --------------------------------------------------

@app.route("/")
def home():
    return send_file(BASE_DIR.parent / "index.html")


# --------------------------------------------------
# Task pages
# --------------------------------------------------

@app.route("/task/1")
@login_required
def task1():
    return send_file(BASE_DIR / "tasks" / "task1.html")


@app.route("/task/2")
@login_required
def task2():
    return send_file(BASE_DIR / "tasks" / "task2.html")


@app.route("/task/3")
@login_required
def task3():
    return send_file(BASE_DIR / "tasks" / "task3.html")


@app.route("/task/4")
@login_required
def task4():
    return send_file(BASE_DIR / "tasks" / "task4.html")


@app.route("/task/5")
@login_required
def task5():
    return send_file(BASE_DIR / "tasks" / "task5.html")


@app.route("/task/6")
@login_required
def task6():
    return send_file(BASE_DIR / "tasks" / "task6.html")


@app.route("/task/7")
@login_required
def task7():
    return send_file(BASE_DIR / "tasks" / "task7.html")


# --------------------------------------------------
# Dashboard
# --------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    return send_file(BASE_DIR / "dashboard.html")


@app.route("/tasks")
@login_required
def tasks():
    return send_file(BASE_DIR / "tasks.html")


# --------------------------------------------------
# Statistics
# --------------------------------------------------



@app.route("/certificate")
@login_required
def certificate():
    user_id = session["user_id"]
    certificate = get_certificate(user_id)

    if certificate is None:
        return jsonify({
            "available": False,
            "locked": True,
            "message": "Complete all 7 tasks and all 45 questions to unlock the certificate."
        })

    return jsonify({
        "available": True,
        "locked": False,
        "certificate_id": certificate["certificate_id"],
        "issued_at": certificate["issued_at"],
        "username": session.get("username")
    })



@app.route("/certificate/download")
@login_required
def download_certificate():
    user_id = session["user_id"]
    certificate = get_certificate(user_id)

    if certificate is None:
        return "Certificate is locked. Complete all 7 tasks and all 45 questions first.", 403

    username = session.get("username", "Learner")
    certificate_id = certificate["certificate_id"]
    issued_at = certificate["issued_at"]

    output_dir = BASE_DIR / "generated_certificates"
    output_dir.mkdir(exist_ok=True)

    safe_username = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in username
    )

    filename = f"FloodGate_{safe_username}_{certificate_id}.pdf"
    pdf_path = output_dir / filename

    page_width, page_height = landscape(A4)

    pdf = canvas.Canvas(str(pdf_path), pagesize=(page_width, page_height))

    # Border
    margin = 15 * mm
    pdf.setLineWidth(2)
    pdf.rect(
        margin,
        margin,
        page_width - 2 * margin,
        page_height - 2 * margin
    )

    # Title
    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 45 * mm,
        "FLOODGATE"
    )

    pdf.setFont("Helvetica", 18)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 58 * mm,
        "Certificate of Completion"
    )

    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 75 * mm,
        "This certificate is presented to"
    )

    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 92 * mm,
        username
    )

    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 110 * mm,
        "for completing the FloodGate DoS Defense & Traffic Monitoring Lab."
    )

    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(
        page_width / 2,
        38 * mm,
        f"Certificate ID: {certificate_id}"
    )

    pdf.drawCentredString(
        page_width / 2,
        30 * mm,
        f"Issued: {issued_at}"
    )

    pdf.drawCentredString(
        page_width / 2,
        22 * mm,
        f"Verify: {os.environ.get(
            "FLOODGATE_PUBLIC_URL",
            request.url_root.rstrip("/")
        )}/verify/{certificate_id}"
    )

    pdf.save()

    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )

@app.route("/verify/<certificate_id>")
def verify_certificate(certificate_id):
    certificate = get_certificate_by_id(certificate_id)

    if certificate is None:
        return """
        <h1>FloodGate Certificate</h1>
        <p>Certificate not found.</p>
        """, 404

    username = escape(certificate["username"])
    certificate_id_safe = escape(certificate["certificate_id"])
    issued_at = escape(certificate["issued_at"])

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FloodGate Certificate Verification</title>
    </head>
    <body>
        <h1>FloodGate</h1>
        <h2>Certificate Verification</h2>
        <p><strong>Status:</strong> Valid</p>
        <p><strong>Learner:</strong> {username}</p>
        <p><strong>Certificate ID:</strong> {certificate_id_safe}</p>
        <p><strong>Issued:</strong> {issued_at}</p>
        <p>This certificate records completion of the FloodGate cybersecurity learning lab.</p>
    </body>
    </html>
    """

@app.route("/progress")
@login_required
def progress():
    user_id = session["user_id"]

    rows = get_completed_questions(user_id)

    completed = {}

    for row in rows:
        task_id = row["task_id"]
        completed.setdefault(task_id, set()).add(row["question_id"])

    result = {}

    for task_id, total in TASK_QUESTION_COUNTS.items():
        count = len(completed.get(task_id, set()))
        result[str(task_id)] = {
            "completed": count,
            "total": total,
            "complete": count >= total
        }

    return jsonify(result)


@app.route("/stats")
def stats():
    elapsed = time.time() - start_time

    rps = total_requests / elapsed if elapsed else 0

    return jsonify({
        "total_requests": total_requests,
        "allowed_requests": allowed_requests,
        "blocked_requests": blocked_requests,
        "requests_per_second": round(rps, 2),
        "tracked_clients": len(clients),
        "rate_limit": LIMIT,
        "window_seconds": WINDOW,
        "completed_tasks": sorted(completed_task_ids)
    })


# --------------------------------------------------
# Security logs
# --------------------------------------------------

@app.route("/logs")
def show_logs():
    return jsonify(logs)


# --------------------------------------------------
# Answer validation — Tasks 1–6
# --------------------------------------------------

TASK_ANSWERS = {

    1: {
        "1": [
            "denial of service",
            "denial-of-service"
        ],

        "2": [
            "make a service unavailable",
            "make a service unavailable to users",
            "make a service unavailable to legitimate users",
            "make the service unavailable",
            "make the service unavailable to users",
            "make the service unavailable to legitimate users",
            "disrupt availability",
            "deny service"
        ],

        "3": [
            "dos uses one source while ddos uses multiple sources",
            "dos uses one source and ddos uses multiple sources",
            "dos uses a single source while ddos uses multiple sources",
            "dos uses one source while ddos is distributed",
            "dos is one source and ddos is distributed",
            "dos uses a single source and ddos uses distributed sources"
        ],

        "4": [
            "local training server",
            "local server",
            "training server",
            "127.0.0.1"
        ]
    },


    2: {
        "1": ["127.0.0.1"],
        "2": ["5000"],
        "3": ["/stats"],
        "4": ["/logs"],
        "5": ["/dashboard"]
    },


    3: {
        "1": ["429", "http 429"],
        "2": ["200", "http 200"],
        "3": ["5", "5 requests"],
        "4": ["20", "20 requests"],
        "5": ["blocked", "block"]
    },


    4: {
        "1": ["/dashboard"],
        "2": ["/logs"],
        "3": ["127.0.0.1"],
        "4": ["blocked"],
        "5": ["429", "http 429"]
    },


    5: {
        "1": [
            "rate limiting",
            "rate limit",
            "rate-limiting"
        ],

        "2": [
            "5",
            "5 requests"
        ],

        "3": [
            "10",
            "10 seconds"
        ],

        "4": [
            "429",
            "http 429"
        ],

        "5": [
            "no"
        ]
    },


    6: {
        "1": ["/stats"],
        "2": ["/logs"],
        "3": ["127.0.0.1"],
        "4": ["blocked"],
        "5": ["429", "http 429"],
        "6": ["15", "15 requests"],
        "7": [
            "rate limiting",
            "rate limit",
            "rate-limiting"
        ]
    }
}


# --------------------------------------------------
# Generic validator for Tasks 1–6
# --------------------------------------------------


# ============================================================
# FLOODGATE V2 — TASK ANSWER VALIDATION
# ============================================================

TASK_ANSWERS = {
    1: {
        1: ["availability"],
        2: ["disrupt service availability", "make the service unavailable", "deny availability"],
        3: ["legitimate traffic"],
        4: ["excessive traffic"],
        5: ["no"],
        6: ["detect unusual traffic patterns and protect service availability",
            "detect unusual traffic patterns",
            "protect service availability"]
    },

    2: {
        1: ["http"],
        2: ["5000"],
        3: ["200"],
        4: ["/stats", "stats"],
        5: ["/logs", "logs"],
        6: ["/dashboard", "dashboard"]
    },

    3: {
        1: ["5"],
        2: ["15"],
        3: ["25", "25%"],
        4: ["75", "75%"],
        5: ["6", "request 6", "6th", "6th request"],
        6: ["200 then 429", "200, 429", "200 429"]
    },

    4: {
        1: ["allowed"],
        2: ["blocked"],
        3: ["one", "single"],
        4: ["127.0.0.1"],
        5: ["requests change from allowed to blocked",
            "allowed to blocked",
            "allowed then blocked",
            "requests become blocked"],
        6: ["it shows an unusual traffic pattern",
            "shows an unusual traffic pattern",
            "unusual traffic pattern",
            "repeated traffic pattern"]
    },

    5: {
        1: ["5"],
        2: ["10", "10 seconds"],
        3: ["429"],
        4: ["no"],
        5: ["they expire", "expire", "old requests expire",
            "they fall outside the window"],
        6: ["it limits excessive requests and protects service resources",
            "limits excessive requests and protects service resources",
            "limits excessive requests",
            "protects service resources"]
    },

    6: {
        1: ["20"],
        2: ["5"],
        3: ["15"],
        4: ["6", "request 6", "6th", "6th request"],
        5: ["yes"],
        6: ["429 responses and blocked log events",
            "429 and blocked",
            "429 responses",
            "blocked log events"],
        7: ["excessive traffic triggered rate limiting",
            "excessive traffic",
            "rate limiting"]
    },

    7: {
        1: ["25", "25%"],
        2: ["75", "75%"],
        3: ["6", "request 6", "6th", "6th request"],
        4: ["0.5", "0.5 requests per second"],
        5: ["yes"],
        6: ["excessive traffic"],
        7: ["/stats, /logs", "/stats /logs", "/logs, /stats",
            "/logs /stats", "stats and logs", "logs and stats"],
        8: ["rate limiting", "rate limit"]
    }
}

TASK_QUESTION_COUNTS = {
    1: 6,
    2: 6,
    3: 6,
    4: 6,
    5: 6,
    6: 7,
    7: 8
}

def issue_certificate_if_complete(user_id):
    completed = get_completed_questions(user_id)

    completed_map = {}

    for row in completed:
        task_id = row["task_id"]
        question_id = row["question_id"]
        completed_map.setdefault(task_id, set()).add(question_id)

    all_complete = all(
        len(completed_map.get(task_id, set())) >= total
        for task_id, total in TASK_QUESTION_COUNTS.items()
    )

    if not all_complete:
        return None

    existing = get_certificate(user_id)

    if existing:
        return existing

    certificate_id = (
        f"FG-{datetime.now().year}-"
        f"{uuid.uuid4().hex[:10].upper()}"
    )

    return create_certificate(user_id, certificate_id)


def answer_matches(task_id, question, answer):
    normalized = normalize_answer(answer)

    if task_id not in TASK_ANSWERS:
        return False

    if question not in TASK_ANSWERS[task_id]:
        return False

    accepted = TASK_ANSWERS[task_id][question]

    # Exact/contains matching for controlled educational answers.
    for item in accepted:
        expected = normalize_answer(item)

        if normalized == expected:
            return True

        if expected in normalized:
            return True

    # Special flexible checks
    if task_id == 1 and question == 2:
        return (
            ("availability" in normalized and
             ("disrupt" in normalized or
              "unavailable" in normalized or
              "deny" in normalized))
        )

    if task_id == 1 and question == 6:
        return (
            ("traffic" in normalized or "pattern" in normalized)
            and
            ("detect" in normalized or "monitor" in normalized)
        )

    if task_id == 4 and question == 5:
        return (
            "allowed" in normalized and
            "blocked" in normalized
        )

    if task_id == 4 and question == 6:
        return (
            "unusual" in normalized
            and
            ("pattern" in normalized or
             "traffic" in normalized)
        )

    if task_id == 5 and question == 6:
        return (
            ("limit" in normalized or "restrict" in normalized)
            and
            ("excessive" in normalized or
             "traffic" in normalized or
             "requests" in normalized)
        )

    if task_id == 6 and question == 6:
        return (
            ("429" in normalized or "too many" in normalized)
            and
            ("blocked" in normalized or "log" in normalized)
        )

    if task_id == 6 and question == 7:
        return (
            ("excessive" in normalized or "traffic" in normalized)
            and
            ("rate" in normalized or "limit" in normalized)
        )

    if task_id == 7 and question == 7:
        return (
            "stats" in normalized
            and
            "logs" in normalized
        )

    if task_id == 7 and question == 8:
        return (
            "rate" in normalized
            and
            "limit" in normalized
        )

    return False


def normalize_answer(value):
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9%./,\s-]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


@app.route("/check/task/<int:task_id>", methods=["POST"])
@login_required
def check_task(task_id):

    data = request.get_json(silent=True) or {}

    question_raw = data.get("question", "")
    answer = data.get("answer", "")

    try:
        question = int(question_raw)
    except (ValueError, TypeError):
        return jsonify({
            "correct": False,
            "error": "Invalid question."
        }), 400

    if task_id not in TASK_QUESTION_COUNTS:
        return jsonify({
            "correct": False,
            "error": "Unknown task."
        }), 404

    if question < 1 or question > TASK_QUESTION_COUNTS[task_id]:
        return jsonify({
            "correct": False,
            "error": "Invalid question."
        }), 400

    correct = answer_matches(task_id, question, answer)

    user_id = session["user_id"]

    if correct:
        mark_question_complete(user_id, task_id, question)

    completed = get_completed_questions(user_id, task_id)

    task_completed = len(completed) >= TASK_QUESTION_COUNTS[task_id]

    certificate = None

    if correct:
        certificate = issue_certificate_if_complete(user_id)

    return jsonify({
        "correct": correct,
        "task_completed": task_completed,
        "certificate_issued": certificate is not None,
        "certificate_id": (
            certificate["certificate_id"]
            if certificate else None
        )
    })


# =========================
# ADMIN PANEL
# =========================

def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped_view


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    import hmac

    if session.get("admin_authenticated"):
        return redirect(url_for("admin_dashboard"))

    error = ""

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        username_ok = hmac.compare_digest(username, ADMIN_USERNAME)
        password_ok = hmac.compare_digest(password, ADMIN_PASSWORD)

        if username_ok and password_ok:
            session.clear()
            session["admin_authenticated"] = True
            session["admin_username"] = ADMIN_USERNAME
            return redirect(url_for("admin_dashboard"))

        error = "Invalid admin credentials."

    return f"""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>FloodGate Admin Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #080b10;
            color: #f5f5f5;
            font-family: Arial, sans-serif;
        }}
        .card {{
            width: min(420px, 90%);
            background: #11161d;
            border: 1px solid #29313b;
            border-radius: 14px;
            padding: 30px;
            box-sizing: border-box;
        }}
        h1 {{ margin-top: 0; }}
        .badge {{
            display: inline-block;
            padding: 6px 10px;
            border-radius: 20px;
            background: #202a35;
            color: #8fd3ff;
            font-size: 12px;
            margin-bottom: 15px;
        }}
        input {{
            width: 100%;
            box-sizing: border-box;
            padding: 12px;
            margin: 8px 0 14px;
            border-radius: 8px;
            border: 1px solid #384452;
            background: #0b0f14;
            color: white;
        }}
        button {{
            width: 100%;
            padding: 12px;
            border: 0;
            border-radius: 8px;
            background: #1677ff;
            color: white;
            font-weight: bold;
            cursor: pointer;
        }}
        .error {{
            background: #35191d;
            border: 1px solid #73323a;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 15px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">FLOODGATE ADMINISTRATOR</div>
        <h1>🛡️ Admin Login</h1>
        {"<div class='error'>" + error + "</div>" if error else ""}
        <form method="post">
            <label>Username</label>
            <input name="username" autocomplete="username" required>

            <label>Password</label>
            <input type="password" name="password"
                   autocomplete="current-password" required>

            <button type="submit">Login to Admin Panel</button>
        </form>
    </div>
</body>
</html>
"""


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_connection()

    user_count = conn.execute(
        "SELECT COUNT(*) AS count FROM users"
    ).fetchone()["count"]

    certificate_count = conn.execute(
        "SELECT COUNT(*) AS count FROM certificates"
    ).fetchone()["count"]

    progress_count = conn.execute(
        "SELECT COUNT(*) AS count FROM progress"
    ).fetchone()["count"]

    users = conn.execute(
        """
        SELECT id, username, email, created_at, last_login
        FROM users
        ORDER BY id DESC
        LIMIT 50
        """
    ).fetchall()

    certificates = conn.execute(
        """
        SELECT certificate_id, issued_at, username
        FROM certificates
        JOIN users ON users.id = certificates.user_id
        ORDER BY certificates.id DESC
        LIMIT 50
        """
    ).fetchall()

    conn.close()

    user_rows = ""

    for user in users:
        username = escape(user["username"])
        email = escape(user["email"])
        created = escape(user["created_at"])
        last_login = escape(user["last_login"] or "Never")

        user_rows += f"""
        <tr>
            <td>{user["id"]}</td>
            <td>{username}</td>
            <td>{email}</td>
            <td>{created}</td>
            <td>{last_login}</td>
        </tr>
        """

    certificate_rows = ""

    for cert in certificates:
        certificate_rows += f"""
        <tr>
            <td>{escape(cert["certificate_id"])}</td>
            <td>{escape(cert["username"])}</td>
            <td>{escape(cert["issued_at"])}</td>
        </tr>
        """

    event_rows = ""

    for event in reversed(logs[-25:]):
        event_rows += f"""
        <tr>
            <td>{escape(str(event.get("time", "")))}</td>
            <td>{escape(str(event.get("ip", "")))}</td>
            <td>{escape(str(event.get("status", "")))}</td>
        </tr>
        """

    return f"""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>FloodGate Admin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            margin: 0;
            background: #080b10;
            color: #f5f5f5;
            font-family: Arial, sans-serif;
        }}
        header {{
            padding: 20px;
            background: #11161d;
            border-bottom: 1px solid #29313b;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 15px;
        }}
        main {{
            width: min(1200px, 94%);
            margin: 25px auto;
        }}
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
        }}
        .card {{
            background: #11161d;
            border: 1px solid #29313b;
            border-radius: 12px;
            padding: 20px;
        }}
        .number {{
            font-size: 32px;
            font-weight: bold;
            margin-top: 8px;
        }}
        section {{
            margin-top: 25px;
        }}
        .table-wrap {{
            overflow-x: auto;
            background: #11161d;
            border: 1px solid #29313b;
            border-radius: 12px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            min-width: 650px;
        }}
        th, td {{
            padding: 11px;
            border-bottom: 1px solid #252d36;
            text-align: left;
        }}
        th {{
            background: #171d25;
        }}
        a {{
            color: #8fd3ff;
            text-decoration: none;
        }}
        .logout {{
            padding: 9px 14px;
            border: 1px solid #485462;
            border-radius: 8px;
        }}
    </style>
</head>
<body>

<header>
    <div>
        <strong>🛡️ FloodGate Admin</strong>
        <div>Administrator: {escape(ADMIN_USERNAME)}</div>
    </div>
    <a class="logout" href="/admin/logout">Logout</a>
</header>

<main>
    <h1>Administration Dashboard</h1>

    <div class="cards">
        <div class="card">
            <div>Registered Users</div>
            <div class="number">{user_count}</div>
        </div>

        <div class="card">
            <div>Certificates Issued</div>
            <div class="number">{certificate_count}</div>
        </div>

        <div class="card">
            <div>Progress Records</div>
            <div class="number">{progress_count}</div>
        </div>

        <div class="card">
            <div>Total Requests</div>
            <div class="number">{total_requests}</div>
        </div>

        <div class="card">
            <div>Allowed Requests</div>
            <div class="number">{allowed_requests}</div>
        </div>

        <div class="card">
            <div>Blocked Requests</div>
            <div class="number">{blocked_requests}</div>
        </div>
    </div>

    <section>
        <h2>👥 Registered Users</h2>
        <div class="table-wrap">
            <table>
                <tr>
                    <th>ID</th>
                    <th>Username</th>
                    <th>Email</th>
                    <th>Created</th>
                    <th>Last Login</th>
                </tr>
                {user_rows}
            </table>
        </div>
    </section>

    <section>
        <h2>🏆 Certificates</h2>
        <div class="table-wrap">
            <table>
                <tr>
                    <th>Certificate ID</th>
                    <th>Learner</th>
                    <th>Issued</th>
                </tr>
                {certificate_rows}
            </table>
        </div>
    </section>

    <section>
        <h2>🛡️ Recent Security Events</h2>
        <div class="table-wrap">
            <table>
                <tr>
                    <th>Time</th>
                    <th>Source</th>
                    <th>Status</th>
                </tr>
                {event_rows}
            </table>
        </div>
    </section>
</main>

</body>
</html>
"""


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_authenticated", None)
    session.pop("admin_username", None)
    return redirect(url_for("admin_login"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
