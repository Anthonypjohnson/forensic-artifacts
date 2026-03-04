import sqlite3
from pathlib import Path
from flask import g, current_app

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db():
    """Return the per-request database connection, creating it if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE_PATH"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        # WAL mode for concurrent read/write; foreign keys enforced
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables from schema.sql if they don't exist."""
    db = get_db()
    with open(SCHEMA_PATH, "r") as f:
        db.executescript(f.read())
    db.commit()


def init_app(app):
    """Register db teardown with the Flask app."""
    app.teardown_appcontext(close_db)
