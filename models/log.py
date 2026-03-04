from database.db import get_db


def get_activity_log(limit=500, editor=None, kind=None):
    """Return unified list of artifact + IOC create/edit events, newest first."""
    db = get_db()

    art_where_parts = []
    art_params = []
    ioc_where_parts = []
    ioc_params = []

    if editor:
        art_where_parts.append("h.editor_name LIKE ?")
        art_params.append(f"%{editor}%")
        ioc_where_parts.append("h.editor_name LIKE ?")
        ioc_params.append(f"%{editor}%")

    art_where = ("WHERE " + " AND ".join(art_where_parts)) if art_where_parts else ""
    ioc_where = ("WHERE " + " AND ".join(ioc_where_parts)) if ioc_where_parts else ""

    artifact_q = f"""
        SELECT
            h.changed_at AS ts,
            'artifact'   AS kind,
            a.id         AS subject_id,
            a.name       AS subject_label,
            CASE WHEN h.snapshot_json = '{{}}' THEN 'created' ELSE 'edited' END AS action,
            h.editor_name,
            h.change_summary AS note
        FROM edit_history h
        JOIN artifacts a ON h.artifact_id = a.id
        {art_where}
    """

    ioc_q = f"""
        SELECT
            h.edited_at AS ts,
            'ioc'       AS kind,
            i.id        AS subject_id,
            COALESCE(
                NULLIF(i.ip_address, ''),
                NULLIF(i.domain, ''),
                NULLIF(i.hash_value, ''),
                NULLIF(i.hostname, ''),
                'IOC #' || CAST(i.id AS TEXT)
            ) AS subject_label,
            CASE WHEN h.ioc_snapshot = '{{}}' THEN 'created' ELSE 'edited' END AS action,
            h.editor_name,
            h.change_summary AS note
        FROM ioc_edit_history h
        JOIN iocs i ON h.ioc_id = i.id
        {ioc_where}
    """

    if kind == "artifact":
        query = artifact_q + " ORDER BY ts DESC LIMIT ?"
        params = art_params + [limit]
    elif kind == "ioc":
        query = ioc_q + " ORDER BY ts DESC LIMIT ?"
        params = ioc_params + [limit]
    else:
        query = (
            f"SELECT * FROM ({artifact_q} UNION ALL {ioc_q})"
            " ORDER BY ts DESC LIMIT ?"
        )
        params = art_params + ioc_params + [limit]

    rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]
