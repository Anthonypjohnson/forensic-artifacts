import json
from database.db import get_db


def insert_history(artifact_id, editor_name, change_summary, artifact_snapshot: dict):
    db = get_db()
    db.execute(
        """
        INSERT INTO edit_history (artifact_id, editor_name, change_summary, snapshot_json)
        VALUES (?, ?, ?, ?)
        """,
        (artifact_id, editor_name, change_summary, json.dumps(artifact_snapshot)),
    )
    db.commit()


def get_history_for_artifact(artifact_id):
    rows = get_db().execute(
        """
        SELECT id, editor_name, change_summary, changed_at, snapshot_json
        FROM edit_history
        WHERE artifact_id = ?
        ORDER BY changed_at DESC
        """,
        (artifact_id,),
    ).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry["snapshot"] = json.loads(entry.pop("snapshot_json"))
        result.append(entry)
    return result
