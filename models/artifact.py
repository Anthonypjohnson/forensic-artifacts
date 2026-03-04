from datetime import datetime, timezone
from database.db import get_db
from models import tag as tag_model


def _row_to_dict(row):
    return dict(row) if row else None


def get_all(search=None, tag_filter=None):
    db = get_db()
    query = """
        SELECT DISTINCT a.id, a.name, a.location, a.tools, a.instructions,
               a.significance, a.created_at, a.updated_at, a.created_by, a.updated_by
        FROM artifacts a
    """
    params = []

    if tag_filter:
        query += """
            JOIN artifact_tags at ON a.id = at.artifact_id
            JOIN tags t ON at.tag_id = t.id
        """

    query += " WHERE 1=1"

    if search:
        query += """
            AND (
                a.name LIKE ? OR a.location LIKE ? OR a.tools LIKE ?
                OR a.instructions LIKE ? OR a.significance LIKE ?
            )
        """
        term = f"%{search}%"
        params.extend([term, term, term, term, term])

    if tag_filter:
        query += " AND t.name = ?"
        params.append(tag_filter)

    query += " ORDER BY a.updated_at DESC"

    rows = db.execute(query, params).fetchall()
    artifacts = []
    for row in rows:
        a = _row_to_dict(row)
        a["tags"] = tag_model.get_for_artifact(a["id"])
        artifacts.append(a)
    return artifacts


def get_by_id(artifact_id):
    row = get_db().execute(
        "SELECT * FROM artifacts WHERE id = ?", (artifact_id,)
    ).fetchone()
    if not row:
        return None
    a = _row_to_dict(row)
    a["tags"] = tag_model.get_for_artifact(artifact_id)
    return a


def create(name, location, tools, instructions, significance, created_by, tags):
    db = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    cur = db.execute(
        """
        INSERT INTO artifacts
            (name, location, tools, instructions, significance, created_at, updated_at, created_by, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, location, tools, instructions, significance, now, now, created_by, created_by),
    )
    db.commit()
    artifact_id = cur.lastrowid
    tag_model.set_tags_for_artifact(artifact_id, tags)
    return artifact_id


def update(artifact_id, name, location, tools, instructions, significance, updated_by, tags):
    db = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    db.execute(
        """
        UPDATE artifacts
        SET name=?, location=?, tools=?, instructions=?, significance=?,
            updated_at=?, updated_by=?
        WHERE id=?
        """,
        (name, location, tools, instructions, significance, now, updated_by, artifact_id),
    )
    db.commit()
    tag_model.set_tags_for_artifact(artifact_id, tags)


def delete(artifact_id):
    db = get_db()
    db.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
    db.commit()
