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
    conn.commit()
    return conn, cur