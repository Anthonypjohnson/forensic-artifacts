from collections import OrderedDict

from flask import Blueprint, render_template, request
from flask_login import login_required

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
    "id", "event_datetime", "event_category", "system", "account",
    "high_level_source", "detailed_source", "notes", "task_id",
    "ioc_id", "linked_task_id", "show_on_timeline",
    "tags", "created_at", "updated_at", "created_by", "updated_by",
]


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
    for ev in events:
        if not ev.get("event_datetime"):
            continue
        row = dict(ev)
        row["tags"] = "; ".join(t["name"] for t in ev["tags"])
        rows.append(row)
    return make_csv_response(_CSV_HEADERS, rows, "timeline.csv")
