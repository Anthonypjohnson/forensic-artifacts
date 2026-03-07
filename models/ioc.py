import json
from datetime import datetime, timezone
from database.db import get_db

IOC_FIELDS = [
    'category', 'severity', 'hostname', 'ip_address', 'domain', 'url',
    'hash_value', 'hash_type', 'filename', 'file_path',
    'registry_key', 'command_line', 'email', 'user_account', 'notes',
    'user_agent', 'mitre_category', 'detection_rule', 'network_port', 'network_protocol',
]

# Priority order for "primary indicator" display on cards
_INDICATOR_PRIORITY = [
    'ip_address', 'domain', 'hash_value', 'filename', 'hostname',
    'url', 'user_agent', 'network_port', 'email', 'registry_key',
    'command_line', 'user_account', 'file_path',
]


def _row_to_dict(row):
    return dict(row) if row else None


def get_primary_indicator(ioc):
    """Return (field_name, value) for the first non-empty indicator in priority order."""
    for field in _INDICATOR_PRIORITY:
        val = ioc.get(field, '')
        if val:
            return field, val
    return 'notes', ioc.get('notes', '')


# ── Queries ─────────────────────────────────────────────────────────────────

def get_all(search=None, category_filter=None, tag_filter=None):
    db = get_db()
    query = """
        SELECT DISTINCT i.id, i.category, i.severity, i.hostname, i.ip_address,
               i.domain, i.url, i.hash_value, i.hash_type, i.filename, i.file_path,
               i.registry_key, i.command_line, i.email, i.user_account, i.notes,
               i.user_agent, i.mitre_category, i.detection_rule, i.network_port,
               i.network_protocol, i.created_at, i.updated_at, i.created_by, i.updated_by
        FROM iocs i
    """
    params = []

    if tag_filter:
        query += """
            JOIN ioc_tag_assignments ita ON i.id = ita.ioc_id
            JOIN ioc_tags it ON ita.tag_id = it.id
        """

    query += " WHERE 1=1"

    if search:
        query += """
            AND (
                i.category LIKE ? OR i.hostname LIKE ? OR i.ip_address LIKE ?
                OR i.domain LIKE ? OR i.url LIKE ? OR i.hash_value LIKE ?
                OR i.filename LIKE ? OR i.file_path LIKE ? OR i.registry_key LIKE ?
                OR i.command_line LIKE ? OR i.email LIKE ? OR i.user_account LIKE ?
                OR i.notes LIKE ? OR i.user_agent LIKE ? OR i.detection_rule LIKE ?
                OR i.network_port LIKE ? OR i.network_protocol LIKE ?
            )
        """
        term = f"%{search}%"
        params.extend([term] * 17)

    if category_filter:
        query += " AND i.category = ?"
        params.append(category_filter)

    if tag_filter:
        query += " AND it.name = ?"
        params.append(tag_filter)

    query += " ORDER BY i.updated_at DESC"

    rows = db.execute(query, params).fetchall()
    iocs = []
    for row in rows:
        ioc = _row_to_dict(row)
        ioc["tags"] = get_tags_for_ioc(ioc["id"])
        iocs.append(ioc)
    return iocs


def get_by_id(ioc_id):
    row = get_db().execute(
        "SELECT * FROM iocs WHERE id = ?", (ioc_id,)
    ).fetchone()
    if not row:
        return None
    ioc = _row_to_dict(row)
    ioc["tags"] = get_tags_for_ioc(ioc_id)
    return ioc


def get_distinct_categories():
    rows = get_db().execute(
        "SELECT DISTINCT category FROM iocs WHERE category != '' ORDER BY category COLLATE NOCASE"
    ).fetchall()
    return [r["category"] for r in rows]


# ── Mutations ────────────────────────────────────────────────────────────────

def create(fields_dict, created_by, tag_names):
    db = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    cur = db.execute(
        """
        INSERT INTO iocs
            (category, severity, hostname, ip_address, domain, url,
             hash_value, hash_type, filename, file_path, registry_key,
             command_line, email, user_account, notes,
             user_agent, mitre_category, detection_rule, network_port, network_protocol,
             created_at, updated_at, created_by, updated_by)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            fields_dict.get('category', ''),
            fields_dict.get('severity', 'Medium'),
            fields_dict.get('hostname', ''),
            fields_dict.get('ip_address', ''),
            fields_dict.get('domain', ''),
            fields_dict.get('url', ''),
            fields_dict.get('hash_value', ''),
            fields_dict.get('hash_type', ''),
            fields_dict.get('filename', ''),
            fields_dict.get('file_path', ''),
            fields_dict.get('registry_key', ''),
            fields_dict.get('command_line', ''),
            fields_dict.get('email', ''),
            fields_dict.get('user_account', ''),
            fields_dict.get('notes', ''),
            fields_dict.get('user_agent', ''),
            fields_dict.get('mitre_category', ''),
            fields_dict.get('detection_rule', ''),
            fields_dict.get('network_port', ''),
            fields_dict.get('network_protocol', ''),
            now, now, created_by, created_by,
        ),
    )
    db.commit()
    ioc_id = cur.lastrowid
    set_tags_for_ioc(ioc_id, tag_names)
    return ioc_id


def update(ioc_id, fields_dict, updated_by, tag_names):
    db = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    db.execute(
        """
        UPDATE iocs
        SET category=?, severity=?, hostname=?, ip_address=?, domain=?, url=?,
            hash_value=?, hash_type=?, filename=?, file_path=?, registry_key=?,
            command_line=?, email=?, user_account=?, notes=?,
            user_agent=?, mitre_category=?, detection_rule=?, network_port=?,
            network_protocol=?, updated_at=?, updated_by=?
        WHERE id=?
        """,
        (
            fields_dict.get('category', ''),
            fields_dict.get('severity', 'Medium'),
            fields_dict.get('hostname', ''),
            fields_dict.get('ip_address', ''),
            fields_dict.get('domain', ''),
            fields_dict.get('url', ''),
            fields_dict.get('hash_value', ''),
            fields_dict.get('hash_type', ''),
            fields_dict.get('filename', ''),
            fields_dict.get('file_path', ''),
            fields_dict.get('registry_key', ''),
            fields_dict.get('command_line', ''),
            fields_dict.get('email', ''),
            fields_dict.get('user_account', ''),
            fields_dict.get('notes', ''),
            fields_dict.get('user_agent', ''),
            fields_dict.get('mitre_category', ''),
            fields_dict.get('detection_rule', ''),
            fields_dict.get('network_port', ''),
            fields_dict.get('network_protocol', ''),
            now, updated_by, ioc_id,
        ),
    )
    db.commit()
    set_tags_for_ioc(ioc_id, tag_names)


def delete(ioc_id):
    db = get_db()
    db.execute("DELETE FROM iocs WHERE id = ?", (ioc_id,))
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


def set_tags_for_ioc(ioc_id, tag_names):
    db = get_db()
    db.execute("DELETE FROM ioc_tag_assignments WHERE ioc_id = ?", (ioc_id,))
    for raw in tag_names:
        name = raw.strip()
        if not name:
            continue
        tag_id = get_or_create_tag(name)
        db.execute(
            "INSERT OR IGNORE INTO ioc_tag_assignments (ioc_id, tag_id) VALUES (?, ?)",
            (ioc_id, tag_id),
        )
    db.commit()
    # Prune orphan ioc_tags
    db.execute(
        "DELETE FROM ioc_tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM ioc_tag_assignments)"
    )
    db.commit()


def get_tags_for_ioc(ioc_id):
    rows = get_db().execute(
        """
        SELECT it.id, it.name
        FROM ioc_tags it
        JOIN ioc_tag_assignments ita ON it.id = ita.tag_id
        WHERE ita.ioc_id = ?
        ORDER BY it.name COLLATE NOCASE
        """,
        (ioc_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_tags_with_counts():
    rows = get_db().execute(
        """
        SELECT it.id, it.name, COUNT(ita.ioc_id) AS count
        FROM ioc_tags it
        LEFT JOIN ioc_tag_assignments ita ON it.id = ita.tag_id
        GROUP BY it.id
        ORDER BY it.name COLLATE NOCASE
        """
    ).fetchall()
    return [dict(r) for r in rows]


# ── History helpers ───────────────────────────────────────────────────────────

def insert_history(ioc_id, editor_name, change_summary, snapshot_dict):
    db = get_db()
    db.execute(
        """
        INSERT INTO ioc_edit_history (ioc_id, editor_name, change_summary, ioc_snapshot)
        VALUES (?, ?, ?, ?)
        """,
        (ioc_id, editor_name, change_summary, json.dumps(snapshot_dict)),
    )
    db.commit()


def get_history_for_ioc(ioc_id):
    rows = get_db().execute(
        """
        SELECT id, editor_name, change_summary, edited_at, ioc_snapshot
        FROM ioc_edit_history
        WHERE ioc_id = ?
        ORDER BY edited_at DESC
        """,
        (ioc_id,),
    ).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry["snapshot"] = json.loads(entry.pop("ioc_snapshot"))
        result.append(entry)
    return result
