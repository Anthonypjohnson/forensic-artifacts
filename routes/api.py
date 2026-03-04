from flask import Blueprint, jsonify, request
from flask_login import login_required

from models import artifact as artifact_model
from models import tag as tag_model
from models import ioc as ioc_model

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/artifacts")
@login_required
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
def list_tags():
    tags = tag_model.get_all_with_counts()
    return jsonify(tags)


@api_bp.route("/iocs")
@login_required
def search_iocs():
    search = request.args.get("q", "").strip() or None
    case_filter = request.args.get("case", "").strip() or None
    iocs = ioc_model.get_all(search=search, case_filter=case_filter)

    result = []
    for ioc in iocs:
        _, primary_val = ioc_model.get_primary_indicator(ioc)
        result.append({
            "id": ioc["id"],
            "case_name": ioc["case_name"],
            "severity": ioc["severity"],
            "primary_indicator": primary_val[:120] + "…" if len(primary_val) > 120 else primary_val,
            "updated_at": ioc["updated_at"],
            "updated_by": ioc["updated_by"],
            "tags": [t["name"] for t in ioc["tags"]],
        })
    return jsonify(result)


@api_bp.route("/ioc-tags")
@login_required
def list_ioc_tags():
    tags = ioc_model.get_all_tags_with_counts()
    return jsonify(tags)
