from database.db import get_db

_DEFAULTS = {
    "timezones": "UTC\nAmerica/New_York\nEurope/London",
}


def get_setting(key: str) -> str:
    db = get_db()
    row = db.execute(
        "SELECT value FROM app_settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else _DEFAULTS.get(key, "")


def set_setting(key: str, value: str) -> None:
    db = get_db()
    db.execute(
        """
        INSERT INTO app_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    db.commit()


def get_timezone_list() -> list:
    """Return ordered list of IANA timezone names from settings."""
    raw = get_setting("timezones")
    tzs = [line.strip() for line in raw.splitlines() if line.strip()]
    # Always include UTC first, deduplicate while preserving order
    seen = set()
    result = []
    for tz in (["UTC"] + tzs):
        if tz not in seen:
            seen.add(tz)
            result.append(tz)
    return result
