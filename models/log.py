from database.db import get_db


def get_activity_log(limit=500, editor=None, kind=None):
    """Return unified list of artifact + IOC + event + task create/edit events, newest first."""
    db = get_db()

    # editor_clause is a hardcoded literal string — the editor *value* flows only into
    # editor_param (a bound parameter), never into the SQL text.  This makes the taint
    # path clear to static analysis tools.
    editor_clause = "AND h.editor_name LIKE ?" if editor else ""
    editor_param  = [f"%{editor}%"]             if editor else []

    artifact_q = (
        "SELECT h.changed_at AS ts, 'artifact' AS kind, a.id AS subject_id,"
        " a.name AS subject_label,"
        " CASE WHEN h.snapshot_json = '{}' THEN 'created' ELSE 'edited' END AS action,"
        " h.editor_name, h.change_summary AS note"
        " FROM edit_history h JOIN artifacts a ON h.artifact_id = a.id"
        " WHERE 1=1 " + editor_clause
    )

    ioc_q = (
        "SELECT h.edited_at AS ts, 'ioc' AS kind, i.id AS subject_id,"
        " COALESCE(NULLIF(i.ip_address,''),NULLIF(i.domain,''),NULLIF(i.hash_value,''),"
        "  NULLIF(i.hostname,''),'IOC #'||CAST(i.id AS TEXT)) AS subject_label,"
        " CASE WHEN h.ioc_snapshot = '{}' THEN 'created' ELSE 'edited' END AS action,"
        " h.editor_name, h.change_summary AS note"
        " FROM ioc_edit_history h JOIN iocs i ON h.ioc_id = i.id"
        " WHERE 1=1 " + editor_clause
    )

    event_q = (
        "SELECT h.edited_at AS ts, 'event' AS kind, e.id AS subject_id,"
        " COALESCE(NULLIF(e.event_category,''),'Event #'||CAST(e.id AS TEXT)) AS subject_label,"
        " CASE WHEN h.snapshot_json = '{}' THEN 'created' ELSE 'edited' END AS action,"
        " h.editor_name, h.change_summary AS note"
        " FROM event_edit_history h JOIN events e ON h.event_id = e.id"
        " WHERE 1=1 " + editor_clause
    )

    task_q = (
        "SELECT h.edited_at AS ts, 'task' AS kind, t.id AS subject_id,"
        " t.title AS subject_label, h.change_summary AS action,"
        " h.editor_name, '' AS note"
        " FROM task_edit_history h JOIN tasks t ON h.task_id = t.id"
        " WHERE 1=1 " + editor_clause
    )

    if kind == "artifact":
        query  = artifact_q + " ORDER BY ts DESC LIMIT ?"
        params = editor_param + [limit]
    elif kind == "ioc":
        query  = ioc_q + " ORDER BY ts DESC LIMIT ?"
        params = editor_param + [limit]
    elif kind == "event":
        query  = event_q + " ORDER BY ts DESC LIMIT ?"
        params = editor_param + [limit]
    elif kind == "task":
        query  = task_q + " ORDER BY ts DESC LIMIT ?"
        params = editor_param + [limit]
    else:
        query = (
            "SELECT * FROM ("
            + artifact_q + " UNION ALL "
            + ioc_q      + " UNION ALL "
            + event_q    + " UNION ALL "
            + task_q
            + ") ORDER BY ts DESC LIMIT ?"
        )
        params = editor_param * 4 + [limit]

    rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]
