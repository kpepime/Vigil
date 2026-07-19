import os
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)
PLACEHOLDER = "%s" if USE_POSTGRES else "?"

if USE_POSTGRES:
    import psycopg2


def get_connection():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL, sslmode="require")
    return sqlite3.connect("signals.db", check_same_thread=False)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id SERIAL PRIMARY KEY,
                fixture_id BIGINT,
                detected_at TEXT,
                outcome TEXT,
                old_pct REAL,
                new_pct REAL,
                change REAL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telegram_subscribers (
                chat_id BIGINT PRIMARY KEY
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fixture_names (
                fixture_id BIGINT PRIMARY KEY,
                team1 TEXT,
                team2 TEXT
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fixture_id INTEGER,
                detected_at TEXT,
                outcome TEXT,
                old_pct REAL,
                new_pct REAL,
                change REAL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telegram_subscribers (
                chat_id INTEGER PRIMARY KEY
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fixture_names (
                fixture_id INTEGER PRIMARY KEY,
                team1 TEXT,
                team2 TEXT
            )
        """)
    conn.commit()
    return conn, cur

def save_fixture_name(fixture_id, team1, team2):
    conn = get_connection()
    cur = conn.cursor()
    if USE_POSTGRES:
        q = f"""
            INSERT INTO fixture_names (fixture_id, team1, team2)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            ON CONFLICT (fixture_id) DO NOTHING
        """
    else:
        q = f"""
            INSERT OR IGNORE INTO fixture_names (fixture_id, team1, team2)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """
    cur.execute(q, (fixture_id, team1, team2))
    conn.commit()


def load_all_fixture_names():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT fixture_id, team1, team2 FROM fixture_names")
    return {row[0]: (row[1], row[2]) for row in cur.fetchall()}