from flask import Blueprint, jsonify, request
from flask_login import login_required

from extensions import limiter
from models import artifact as artifact_model
from models import tag as tag_model
from models import ioc as ioc_model
from models import event as event_model
from models import task as task_model

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/artifacts")
@login_required
@limiter.limit("20 per minute")
def search_artifacts():
    search = request.args.get("q", "").strip() or None
    tag_filter = request.args.get("tag", "").strip() or None
    artifacts = artifact_model.get_all(search=search, tag_filter=tag_filter)

    result = []
    for a in artifacts:
        result.append({
            "id": a["id"],
            "name": a["name"],
            "location": a["location"][:120] + "…" if len(a["location"]) > 120 else a["location"],
            "tools": a["tools"],
            "updated_at": a["updated_at"],
            "updated_by": a["updated_by"],
            "tags": [t["name"] for t in a["tags"]],
        })
    return jsonify(result)


@api_bp.route("/tags")
@login_required
@limiter.limit("20 per minute")
def list_tags():
    tags = tag_model.get_all_with_counts()
    return jsonify(tags)


@api_bp.route("/iocs")
@login_required
@limiter.limit("20 per minute")
def search_iocs():
    search = request.args.get("q", "").strip() or None
    category_filter = request.args.get("category", "").strip() or None
    iocs = ioc_model.get_all(search=search, category_filter=category_filter)

    result = []
    for ioc in iocs:
        _, primary_val = ioc_model.get_primary_indicator(ioc)
        result.append({
            "id": ioc["id"],
            "category": ioc["category"],
            "severity": ioc["severity"],
            "primary_indicator": primary_val[:120] + "…" if len(primary_val) > 120 else primary_val,
            "updated_at": ioc["updated_at"],
            "updated_by": ioc["updated_by"],
            "tags": [t["name"] for t in ioc["tags"]],
        })
    return jsonify(result)


@api_bp.route("/ioc-tags")
@login_required
@limiter.limit("20 per minute")
def list_ioc_tags():
    tags = ioc_model.get_all_tags_with_counts()
    return jsonify(tags)


@api_bp.route("/tasks")
@login_required
@limiter.limit("20 per minute")
def list_tasks():
    tasks = task_model.get_all()
    return jsonify([
        {
            "id": t["id"],
            "title": t["title"],
            "status": t["status"],
            "priority": t["priority"],
            "assignee": t["assignee"],
        }
        for t in tasks
    ])


@api_bp.route("/events")
@login_required
@limiter.limit("20 per minute")
def search_events():
    search = request.args.get("q", "").strip() or None
    ioc_filter = request.args.get("ioc", "").strip()
    tag_filter = request.args.get("tag", "").strip() or None

    events = event_model.get_all(
        search=search,
        ioc_filter=int(ioc_filter) if ioc_filter.isdigit() else None,
        tag_filter=tag_filter,
    )

    result = []
    for ev in events:
        result.append({
            "id": ev["id"],
            "event_datetime": ev["event_datetime"] or "",
            "system": ev["system"] or "",
            "account": ev["account"] or "",
            "event_category": ev["event_category"] or "",
            "ioc_id": ev["ioc_id"],
            "show_on_timeline": bool(ev["show_on_timeline"]),
            "high_level_source": ev["high_level_source"] or "",
            "tags": [t["name"] for t in ev["tags"]],
        })
    return jsonify(result)
