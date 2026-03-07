import json
from datetime import datetime, timezone
from database.db import get_db
from models.event import get_tags_for_event

TASK_FIELDS = ['title', 'status', 'priority', 'assignee', 'description', 'notes']


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_dict(row):
    return dict(row) if row else None


def get_all(search=None, status_filter=None, assignee_filter=None, priority_filter=None):
    db = get_db()
    query = """
        SELECT t.id, t.title, t.status, t.priority, t.assignee,
               t.description, t.notes, t.created_at, t.updated_at,
               t.created_by, t.updated_by,
               COUNT(e.id) AS event_count
        FROM tasks t
        LEFT JOIN events e ON e.linked_task_id = t.id
    """
    params = []
    conditions = []

    if search:
        conditions.append(
            "(t.title LIKE ? OR t.description LIKE ? OR t.notes LIKE ? OR t.assignee LIKE ?)"
        )
        term = f"%{search}%"
        params.extend([term] * 4)

    if status_filter:
        conditions.append("t.status = ?")
        params.append(status_filter)

    if assignee_filter:
        conditions.append("t.assignee LIKE ?")
        params.append(f"%{assignee_filter}%")

    if priority_filter:
        conditions.append("t.priority = ?")
        params.append(priority_filter)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " GROUP BY t.id ORDER BY t.updated_at DESC"

    rows = db.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_by_id(task_id):
    row = get_db().execute(
        """
        SELECT t.id, t.title, t.status, t.priority, t.assignee,
               t.description, t.notes, t.created_at, t.updated_at,
               t.created_by, t.updated_by
        FROM tasks t WHERE t.id = ?
        """,
        (task_id,),
    ).fetchone()
    if not row:
        return None
    task = _row_to_dict(row)
    task["events"] = get_events_for_task(task_id)
    return task


def create(fields_dict, created_by):
    db = get_db()
    now = _now()
    cur = db.execute(
        """
        INSERT INTO tasks (title, status, priority, assignee, description, notes,
                           created_at, updated_at, created_by, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fields_dict.get('title', ''),
            fields_dict.get('status', 'Open'),
            fields_dict.get('priority', 'Medium'),
            fields_dict.get('assignee') or None,
            fields_dict.get('description', ''),
            fields_dict.get('notes', ''),
            now, now, created_by, created_by,
        ),
    )
    db.commit()
    return cur.lastrowid


def update(task_id, fields_dict, updated_by):
    db = get_db()
    db.execute(
        """
        UPDATE tasks
        SET title=?, status=?, priority=?, assignee=?, description=?, notes=?,
            updated_at=?, updated_by=?
        WHERE id=?
        """,
        (
            fields_dict.get('title', ''),
            fields_dict.get('status', 'Open'),
            fields_dict.get('priority', 'Medium'),
            fields_dict.get('assignee') or None,
            fields_dict.get('description', ''),
            fields_dict.get('notes', ''),
            _now(), updated_by, task_id,
        ),
    )
    db.commit()


def delete(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()


def claim(task_id, username, release=False):
    db = get_db()
    now = _now()
    if release:
        db.execute(
            "UPDATE tasks SET assignee=NULL, updated_at=?, updated_by=? WHERE id=?",
            (now, username, task_id),
        )
    else:
        db.execute(
            """
            UPDATE tasks
            SET assignee=?,
                status=CASE WHEN status='Open' THEN 'In Progress' ELSE status END,
                updated_at=?, updated_by=?
            WHERE id=?
            """,
            (username, now, username, task_id),
        )
    db.commit()


def get_events_for_task(task_id):
    rows = get_db().execute(
        """
        SELECT e.id, e.ioc_id, e.show_on_timeline, e.event_category,
               e.system, e.account, e.event_datetime, e.high_level_source,
               e.detailed_source, e.notes, e.screenshot_path, e.task_id,
               e.linked_task_id, e.created_at, e.updated_at, e.created_by, e.updated_by
        FROM events e
        WHERE e.linked_task_id = ?
        ORDER BY e.event_datetime DESC, e.created_at DESC
        """,
        (task_id,),
    ).fetchall()
    events = []
    for row in rows:
        event = _row_to_dict(row)
        event["tags"] = get_tags_for_event(event["id"])
        events.append(event)
    return events


def insert_history(task_id, editor_name, change_summary, snapshot_dict):
    db = get_db()
    db.execute(
        """
        INSERT INTO task_edit_history (task_id, editor_name, change_summary, snapshot_json)
        VALUES (?, ?, ?, ?)
        """,
        (task_id, editor_name, change_summary, json.dumps(snapshot_dict)),
    )
    db.commit()


def get_all_tasks_brief():
    rows = get_db().execute(
        "SELECT id, title, status FROM tasks ORDER BY updated_at DESC"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]
