import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "floodgate.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            certificate_id TEXT NOT NULL UNIQUE,
            issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, task_id, question_id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


def create_user(username, email, password):
    password_hash = generate_password_hash(password)
    conn = get_connection()

    try:
        cursor = conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def authenticate_user(username, password):
    conn = get_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    conn.close()

    if user and check_password_hash(user["password_hash"], password):
        return user

    return None


def update_last_login(user_id):
    conn = get_connection()

    conn.execute(
        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()


def mark_question_complete(user_id, task_id, question_id):
    conn = get_connection()

    conn.execute(
        """
        INSERT OR IGNORE INTO progress (user_id, task_id, question_id)
        VALUES (?, ?, ?)
        """,
        (user_id, task_id, question_id)
    )

    conn.commit()
    conn.close()


def get_completed_questions(user_id, task_id=None):
    conn = get_connection()

    if task_id is None:
        rows = conn.execute(
            """
            SELECT task_id, question_id
            FROM progress
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT task_id, question_id
            FROM progress
            WHERE user_id = ? AND task_id = ?
            """,
            (user_id, task_id)
        ).fetchall()

    conn.close()

    return rows


def get_certificate(user_id):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT certificate_id, issued_at
        FROM certificates
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    conn.close()
    return row


def create_certificate(user_id, certificate_id):
    conn = get_connection()

    conn.execute(
        """
        INSERT OR IGNORE INTO certificates (user_id, certificate_id)
        VALUES (?, ?)
        """,
        (user_id, certificate_id)
    )

    conn.commit()

    row = conn.execute(
        """
        SELECT certificate_id, issued_at
        FROM certificates
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    conn.close()
    return row


def get_certificate_by_id(certificate_id):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT
            certificates.certificate_id,
            certificates.issued_at,
            users.username
        FROM certificates
        JOIN users ON users.id = certificates.user_id
        WHERE certificates.certificate_id = ?
        """,
        (certificate_id,)
    ).fetchone()

    conn.close()
    return row
