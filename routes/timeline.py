from collections import OrderedDict

from flask import Blueprint, render_template, request
from flask_login import login_required

from database.db import get_db
from models import event as event_model
from utils.csv_io import make_csv_response

timeline_bp = Blueprint("timeline", __name__, url_prefix="/timeline")


@timeline_bp.route("/")
@login_required
def index():
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    system_filter = request.args.get("system", "").strip()
    ioc_filter = request.args.get("ioc", "").strip()
    category_filter = request.args.get("category", "").strip()
    tag_filter = request.args.get("tag", "").strip()

    events = event_model.get_all(
        ioc_filter=int(ioc_filter) if ioc_filter.isdigit() else None,
        system_filter=system_filter or None,
        tag_filter=tag_filter or None,
        date_from=date_from or None,
        date_to=date_to or None,
        category_filter=category_filter or None,
    )

    # Filter out events with no datetime and group by date
    grouped = OrderedDict()
    for event in events:
        dt = event.get("event_datetime") or ""
        if not dt:
            continue
        date_key = dt[:10]  # YYYY-MM-DD
        grouped.setdefault(date_key, []).append(event)

    all_iocs = event_model.get_all_iocs_brief()
    all_tags = event_model.get_all_event_tags_with_counts()

    return render_template(
        "timeline.html",
        grouped=grouped,
        all_iocs=all_iocs,
        all_tags=all_tags,
        date_from=date_from,
        date_to=date_to,
        system_filter=system_filter,
        ioc_filter=ioc_filter,
        category_filter=category_filter,
        tag_filter=tag_filter,
    )


_CSV_HEADERS = [
    # Event fields
    "id", "event_datetime", "event_category", "system", "account",
    "high_level_source", "detailed_source", "notes", "task_id",
    "ioc_id", "linked_task_id", "show_on_timeline",
    "tags", "created_at", "updated_at", "created_by", "updated_by",
    # Linked IOC fields
    "ioc_category", "ioc_severity", "ioc_hostname", "ioc_ip_address", "ioc_domain",
    "ioc_url", "ioc_hash_value", "ioc_hash_type", "ioc_filename", "ioc_file_path",
    "ioc_registry_key", "ioc_command_line", "ioc_email", "ioc_user_account", "ioc_notes",
    "ioc_user_agent", "ioc_mitre_category", "ioc_detection_rule",
    "ioc_network_port", "ioc_network_protocol",
    # Linked task fields
    "task_title", "task_status", "task_priority", "task_assignee",
    "task_description", "task_notes",
]


def _enrich_events(events):
    """Attach linked IOC and task fields to each event dict (2 bulk queries)."""
    if not events:
        return events

    ioc_ids = {ev["ioc_id"] for ev in events if ev.get("ioc_id")}
    task_ids = {ev["linked_task_id"] for ev in events if ev.get("linked_task_id")}

    ioc_map = {}
    if ioc_ids:
        ph = ",".join("?" * len(ioc_ids))
        rows = get_db().execute(
            f"SELECT id, category, severity, hostname, ip_address, domain, url, "
            f"hash_value, hash_type, filename, file_path, registry_key, command_line, "
            f"email, user_account, notes, user_agent, mitre_category, detection_rule, "
            f"network_port, network_protocol FROM iocs WHERE id IN ({ph})",
            list(ioc_ids),
        ).fetchall()
        ioc_map = {r["id"]: dict(r) for r in rows}

    task_map = {}
    if task_ids:
        ph = ",".join("?" * len(task_ids))
        rows = get_db().execute(
            f"SELECT id, title, status, priority, assignee, description, notes "
            f"FROM tasks WHERE id IN ({ph})",
            list(task_ids),
        ).fetchall()
        task_map = {r["id"]: dict(r) for r in rows}

    ioc_fields = [
        "category", "severity", "hostname", "ip_address", "domain", "url",
        "hash_value", "hash_type", "filename", "file_path", "registry_key",
        "command_line", "email", "user_account", "notes", "user_agent",
        "mitre_category", "detection_rule", "network_port", "network_protocol",
    ]
    task_fields = ["title", "status", "priority", "assignee", "description", "notes"]

    for ev in events:
        ioc = ioc_map.get(ev.get("ioc_id")) or {}
        task = task_map.get(ev.get("linked_task_id")) or {}
        for f in ioc_fields:
            ev[f"ioc_{f}"] = ioc.get(f, "")
        for f in task_fields:
            ev[f"task_{f}"] = task.get(f, "")

    return events


@timeline_bp.route("/export")
@login_required
def export_csv():
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    system_filter = request.args.get("system", "").strip()
    ioc_filter = request.args.get("ioc", "").strip()
    category_filter = request.args.get("category", "").strip()
    tag_filter = request.args.get("tag", "").strip()

    events = event_model.get_all(
        ioc_filter=int(ioc_filter) if ioc_filter.isdigit() else None,
        system_filter=system_filter or None,
        tag_filter=tag_filter or None,
        date_from=date_from or None,
        date_to=date_to or None,
        category_filter=category_filter or None,
    )
    rows = []
    for ev in _enrich_events([e for e in events if e.get("event_datetime")]):
        row = dict(ev)
        row["tags"] = "; ".join(t["name"] for t in ev["tags"])
        rows.append(row)
    return make_csv_response(_CSV_HEADERS, rows, "timeline.csv")
