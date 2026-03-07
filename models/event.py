import json
import os
from datetime import datetime, timezone
from database.db import get_db

EVENT_FIELDS = [
    'ioc_id', 'show_on_timeline', 'event_category', 'system', 'account',
    'event_datetime', 'high_level_source', 'detailed_source', 'notes',
    'screenshot_path', 'task_id', 'linked_task_id',
]


def _row_to_dict(row):
    return dict(row) if row else None


# ── Queries ─────────────────────────────────────────────────────────────────

def get_all(search=None, ioc_filter=None, system_filter=None, account_filter=None,
            task_id_filter=None, source_filter=None, tag_filter=None,
            date_from=None, date_to=None, category_filter=None):
    db = get_db()
    query = """
        SELECT DISTINCT e.id, e.ioc_id, e.show_on_timeline, e.event_category,
               e.system, e.account, e.event_datetime, e.high_level_source,
               e.detailed_source, e.notes, e.screenshot_path, e.task_id,
               e.linked_task_id,
               e.created_at, e.updated_at, e.created_by, e.updated_by
        FROM events e
    """
    params = []

    if tag_filter:
        query += """
            JOIN event_tag_assignments eta ON e.id = eta.event_id
            JOIN ioc_tags it ON eta.tag_id = it.id
        """

    query += " WHERE 1=1"

    if search:
        query += """
            AND (
                e.system LIKE ? OR e.account LIKE ? OR e.notes LIKE ?
                OR e.high_level_source LIKE ? OR e.detailed_source LIKE ?
                OR e.event_category LIKE ?
            )
        """
        term = f"%{search}%"
        params.extend([term] * 6)

    if ioc_filter:
        query += " AND e.ioc_id = ?"
        params.append(ioc_filter)

    if system_filter:
        query += " AND e.system LIKE ?"
        params.append(f"%{system_filter}%")

    if account_filter:
        query += " AND e.account LIKE ?"
        params.append(f"%{account_filter}%")

    if task_id_filter:
        query += " AND e.task_id = ?"
        params.append(task_id_filter)

    if source_filter:
        query += " AND (e.high_level_source LIKE ? OR e.detailed_source LIKE ?)"
        params.extend([f"%{source_filter}%"] * 2)

    if category_filter:
        query += " AND e.event_category LIKE ?"
        params.append(f"%{category_filter}%")

    if date_from:
        query += " AND e.event_datetime >= ?"
        params.append(date_from)

    if date_to:
        query += " AND e.event_datetime <= ?"
        params.append(date_to + "T23:59:59")

    if tag_filter:
        query += " AND it.name = ?"
        params.append(tag_filter)

    query += " ORDER BY e.event_datetime DESC, e.created_at DESC"

    rows = db.execute(query, params).fetchall()
    events = []
    for row in rows:
        event = _row_to_dict(row)
        event["tags"] = get_tags_for_event(event["id"])
        events.append(event)
    return events


def get_by_id(event_id):
    row = get_db().execute(
        "SELECT * FROM events WHERE id = ?", (event_id,)
    ).fetchone()
    if not row:
        return None
    event = _row_to_dict(row)
    event["tags"] = get_tags_for_event(event_id)
    if event.get("ioc_id"):
        ioc_row = get_db().execute(
            """SELECT id, category, severity, hostname, ip_address, domain, url,
                      hash_value, filename FROM iocs WHERE id = ?""",
            (event["ioc_id"],)
        ).fetchone()
        event["linked_ioc"] = _row_to_dict(ioc_row)
    else:
        event["linked_ioc"] = None
    if event.get("linked_task_id"):
        task_row = get_db().execute(
            "SELECT id, title, status FROM tasks WHERE id = ?",
            (event["linked_task_id"],)
        ).fetchone()
        event["linked_task"] = _row_to_dict(task_row)
    else:
        event["linked_task"] = None
    return event


def get_all_iocs_brief():
    rows = get_db().execute(
        """SELECT id, category, hostname, ip_address, domain, url, hash_value,
                  filename, email FROM iocs ORDER BY id DESC"""
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        for field in ['ip_address', 'domain', 'hash_value', 'filename',
                      'hostname', 'url', 'email']:
            val = d.get(field, '')
            if val:
                label = f"IOC #{d['id']} — {val[:60]}"
                break
        else:
            label = f"IOC #{d['id']}"
        result.append({'id': d['id'], 'label': label})
    return result


def get_all_event_tags_with_counts():
    rows = get_db().execute(
        """
        SELECT it.id, it.name, COUNT(eta.event_id) AS count
        FROM ioc_tags it
        JOIN event_tag_assignments eta ON it.id = eta.tag_id
        GROUP BY it.id
        ORDER BY it.name COLLATE NOCASE
        """
    ).fetchall()
    return [dict(r) for r in rows]


# ── Mutations ────────────────────────────────────────────────────────────────

def create(fields_dict, created_by, tag_names):
    db = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ioc_id = fields_dict.get('ioc_id') or None
    linked_task_id = fields_dict.get('linked_task_id') or None
    cur = db.execute(
        """
        INSERT INTO events
            (ioc_id, show_on_timeline, event_category, system, account,
             event_datetime, high_level_source, detailed_source, notes,
             screenshot_path, task_id, linked_task_id,
             created_at, updated_at, created_by, updated_by)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            ioc_id,
            1 if fields_dict.get('show_on_timeline', True) else 0,
            fields_dict.get('event_category', ''),
            fields_dict.get('system', ''),
            fields_dict.get('account', ''),
            fields_dict.get('event_datetime', ''),
            fields_dict.get('high_level_source', ''),
            fields_dict.get('detailed_source', ''),
            fields_dict.get('notes', ''),
            fields_dict.get('screenshot_path', ''),
            fields_dict.get('task_id', ''),
            linked_task_id,
            now, now, created_by, created_by,
        ),
    )
    db.commit()
    event_id = cur.lastrowid
    set_tags_for_event(event_id, tag_names)
    return event_id


def update(event_id, fields_dict, updated_by, tag_names):
    db = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ioc_id = fields_dict.get('ioc_id') or None
    linked_task_id = fields_dict.get('linked_task_id') or None
    db.execute(
        """
        UPDATE events
        SET ioc_id=?, show_on_timeline=?, event_category=?, system=?, account=?,
            event_datetime=?, high_level_source=?, detailed_source=?, notes=?,
            screenshot_path=?, task_id=?, linked_task_id=?, updated_at=?, updated_by=?
        WHERE id=?
        """,
        (
            ioc_id,
            1 if fields_dict.get('show_on_timeline', True) else 0,
            fields_dict.get('event_category', ''),
            fields_dict.get('system', ''),
            fields_dict.get('account', ''),
            fields_dict.get('event_datetime', ''),
            fields_dict.get('high_level_source', ''),
            fields_dict.get('detailed_source', ''),
            fields_dict.get('notes', ''),
            fields_dict.get('screenshot_path', ''),
            fields_dict.get('task_id', ''),
            linked_task_id,
            now, updated_by, event_id,
        ),
    )
    db.commit()
    set_tags_for_event(event_id, tag_names)


def delete(event_id):
    db = get_db()
    row = db.execute(
        "SELECT screenshot_path FROM events WHERE id = ?", (event_id,)
    ).fetchone()
    if row and row["screenshot_path"]:
        try:
            os.remove(os.path.join("static", "uploads", "events", row["screenshot_path"]))
        except OSError:
            pass
    db.execute("DELETE FROM events WHERE id = ?", (event_id,))
    db.commit()


# ── Tag helpers ───────────────────────────────────────────────────────────────

def get_or_create_tag(name):
    name = name.strip()
    db = get_db()
    row = db.execute("SELECT id FROM ioc_tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO ioc_tags (name) VALUES (?)", (name,))
    db.commit()
    return cur.lastrowid


def set_tags_for_event(event_id, tag_names):
    db = get_db()
    db.execute("DELETE FROM event_tag_assignments WHERE event_id = ?", (event_id,))
    for raw in tag_names:
        name = raw.strip()
        if not name:
            continue
        tag_id = get_or_create_tag(name)
        db.execute(
            "INSERT OR IGNORE INTO event_tag_assignments (event_id, tag_id) VALUES (?, ?)",
            (event_id, tag_id),
        )
    db.commit()


def get_tags_for_event(event_id):
    rows = get_db().execute(
        """
        SELECT it.id, it.name
        FROM ioc_tags it
        JOIN event_tag_assignments eta ON it.id = eta.tag_id
        WHERE eta.event_id = ?
        ORDER BY it.name COLLATE NOCASE
        """,
        (event_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── History helpers ───────────────────────────────────────────────────────────

def insert_history(event_id, editor_name, change_summary, snapshot_dict):
    db = get_db()
    db.execute(
        """
        INSERT INTO event_edit_history (event_id, editor_name, change_summary, snapshot_json)
        VALUES (?, ?, ?, ?)
        """,
        (event_id, editor_name, change_summary, json.dumps(snapshot_dict)),
    )
    db.commit()


def get_history_for_event(event_id):
    rows = get_db().execute(
        """
        SELECT id, editor_name, change_summary, edited_at, snapshot_json
        FROM event_edit_history
        WHERE event_id = ?
        ORDER BY edited_at DESC
        """,
        (event_id,),
    ).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry["snapshot"] = json.loads(entry.pop("snapshot_json") or '{}')
        result.append(entry)
    return result
