from database.db import get_db


def get_all_with_counts():
    """Return all tags with the number of artifacts using each."""
    rows = get_db().execute(
        """
        SELECT t.id, t.name, COUNT(at.artifact_id) AS count
        FROM tags t
        LEFT JOIN artifact_tags at ON t.id = at.tag_id
        GROUP BY t.id
        ORDER BY t.name COLLATE NOCASE
        """
    ).fetchall()
    return [dict(r) for r in rows]


def get_for_artifact(artifact_id):
    rows = get_db().execute(
        """
        SELECT t.id, t.name
        FROM tags t
        JOIN artifact_tags at ON t.id = at.tag_id
        WHERE at.artifact_id = ?
        ORDER BY t.name COLLATE NOCASE
        """,
        (artifact_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_or_create(name):
    """Return tag id for name, creating it if it doesn't exist."""
    name = name.strip()
    db = get_db()
    row = db.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    db.commit()
    return cur.lastrowid


def set_tags_for_artifact(artifact_id, tag_names):
    """Replace the tag set for an artifact with tag_names (list of strings)."""
    db = get_db()
    db.execute("DELETE FROM artifact_tags WHERE artifact_id = ?", (artifact_id,))
    for raw in tag_names:
        name = raw.strip()
        if not name:
            continue
        tag_id = get_or_create(name)
        db.execute(
            "INSERT OR IGNORE INTO artifact_tags (artifact_id, tag_id) VALUES (?, ?)",
            (artifact_id, tag_id),
        )
    db.commit()
    # Prune orphan tags
    db.execute(
        "DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM artifact_tags)"
    )
    db.commit()
