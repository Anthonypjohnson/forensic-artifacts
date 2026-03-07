from datetime import datetime, timezone, timedelta
from flask_login import UserMixin
from database.db import get_db

LOCKOUT_DURATION_MINUTES = 15
MAX_FAILED_ATTEMPTS = 5


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.password_hash = row["password_hash"]
        self.is_admin = bool(row["is_admin"])
        self._is_active = bool(row["is_active"])
        self.failed_attempts = row["failed_attempts"]
        self.locked_until = row["locked_until"]
        self.created_at = row["created_at"]
        self.last_login = row["last_login"]

    @property
    def is_active(self):
        return self._is_active

    def get_id(self):
        return str(self.id)

    def is_locked(self):
        if not self.locked_until:
            return False
        lock_time = datetime.fromisoformat(self.locked_until).replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < lock_time

    def lock_expires_at(self):
        if not self.locked_until:
            return None
        return datetime.fromisoformat(self.locked_until).replace(tzinfo=timezone.utc)


def get_by_id(user_id):
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return User(row) if row else None


def get_by_username(username):
    row = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return User(row) if row else None


def get_all():
    rows = get_db().execute(
        "SELECT * FROM users ORDER BY username COLLATE NOCASE"
    ).fetchall()
    return [User(r) for r in rows]


def create_user(username, password_hash, is_admin=False):
    db = get_db()
    db.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
        (username, password_hash, 1 if is_admin else 0),
    )
    db.commit()


def update_password(user_id, new_hash):
    db = get_db()
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    db.commit()


def record_failed_attempt(user_id):
    db = get_db()
    db.execute(
        "UPDATE users SET failed_attempts = failed_attempts + 1 WHERE id = ?",
        (user_id,),
    )
    # Check if we've hit the threshold and set lockout
    row = db.execute("SELECT failed_attempts FROM users WHERE id = ?", (user_id,)).fetchone()
    if row and row["failed_attempts"] >= MAX_FAILED_ATTEMPTS:
        lock_until = (
            datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.execute("UPDATE users SET locked_until = ? WHERE id = ?", (lock_until, user_id))
    db.commit()


def record_successful_login(user_id):
    db = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.execute(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?",
        (now, user_id),
    )
    db.commit()


def clear_lockout_if_expired(user_id):
    """If lock window has passed, reset lock state. Returns True if account is now unlocked."""
    row = get_db().execute(
        "SELECT locked_until FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row or not row["locked_until"]:
        return True
    lock_time = datetime.fromisoformat(row["locked_until"]).replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= lock_time:
        db = get_db()
        db.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (user_id,),
        )
        db.commit()
        return True
    return False


def set_active(user_id, active):
    db = get_db()
    db.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if active else 0, user_id))
    db.commit()
