import json as _json

import bleach
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from forms.artifact_form import ArtifactForm
from models import artifact as artifact_model
from models import history as history_model
from models import tag as tag_model
from utils.csv_io import make_csv_response, make_template_csv, parse_csv_upload

artifacts_bp = Blueprint("artifacts", __name__)

ALLOWED_TAGS = []  # Strip all HTML — plain text only
ALLOWED_ATTRS = {}


def _sanitize(text):
    return bleach.clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


def _sanitize_artifact_fields(form):
    return {
        "name": _sanitize(form.name.data),
        "location": _sanitize(form.location.data),
        "tools": _sanitize(form.tools.data),
        "instructions": _sanitize(form.instructions.data),
        "significance": _sanitize(form.significance.data),
        "tags": [_sanitize(t) for t in form.tags.data.split(",") if t.strip()],
        "editor_name": _sanitize(form.editor_name.data),
        "change_note": _sanitize(form.change_note.data),
    }


@artifacts_bp.route("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    tag_filter = request.args.get("tag", "").strip()
    artifacts = artifact_model.get_all(
        search=search or None,
        tag_filter=tag_filter or None,
    )
    all_tags = tag_model.get_all_with_counts()
    return render_template(
        "index.html",
        artifacts=artifacts,
        all_tags=all_tags,
        search=search,
        tag_filter=tag_filter,
    )


@artifacts_bp.route("/artifact/new", methods=["GET", "POST"])
@login_required
def new_artifact():
    form = ArtifactForm()
    if form.validate_on_submit():
        fields = _sanitize_artifact_fields(form)
        editor = current_user.username
        artifact_id = artifact_model.create(
            name=fields["name"],
            location=fields["location"],
            tools=fields["tools"],
            instructions=fields["instructions"],
            significance=fields["significance"],
            created_by=editor,
            tags=fields["tags"],
        )
        history_model.insert_history(
            artifact_id=artifact_id,
            editor_name=editor,
            change_summary=fields["change_note"],
            artifact_snapshot={},  # No prior state for new artifacts
        )
        flash("Artifact created.", "success")
        return redirect(url_for("artifacts.detail", artifact_id=artifact_id))
    form.editor_name.data = current_user.username
    return render_template("artifact_form.html", form=form, title="New Artifact")


@artifacts_bp.route("/artifact/<int:artifact_id>")
@login_required
def detail(artifact_id):
    artifact = artifact_model.get_by_id(artifact_id)
    if not artifact:
        abort(404)
    history = history_model.get_history_for_artifact(artifact_id)
    return render_template("artifact_detail.html", artifact=artifact, history=history)


@artifacts_bp.route("/artifact/<int:artifact_id>/edit", methods=["GET", "POST"])
@login_required
def edit_artifact(artifact_id):
    artifact = artifact_model.get_by_id(artifact_id)
    if not artifact:
        abort(404)

    form = ArtifactForm()

    if form.validate_on_submit():
        fields = _sanitize_artifact_fields(form)
        editor = current_user.username
        # Save snapshot BEFORE applying changes
        snapshot = {k: artifact[k] for k in
                    ("name", "location", "tools", "instructions", "significance")}
        snapshot["tags"] = [t["name"] for t in artifact["tags"]]

        artifact_model.update(
            artifact_id=artifact_id,
            name=fields["name"],
            location=fields["location"],
            tools=fields["tools"],
            instructions=fields["instructions"],
            significance=fields["significance"],
            updated_by=editor,
            tags=fields["tags"],
        )
        history_model.insert_history(
            artifact_id=artifact_id,
            editor_name=editor,
            change_summary=fields["change_note"],
            artifact_snapshot=snapshot,
        )
        flash("Artifact updated.", "success")
        return redirect(url_for("artifacts.detail", artifact_id=artifact_id))

    if request.method == "GET":
        form.name.data = artifact["name"]
        form.location.data = artifact["location"]
        form.tools.data = artifact["tools"]
        form.instructions.data = artifact["instructions"]
        form.significance.data = artifact["significance"]
        form.tags.data = ", ".join(t["name"] for t in artifact["tags"])

    form.editor_name.data = current_user.username
    return render_template(
        "artifact_form.html",
        form=form,
        title=f"Edit — {artifact['name']}",
        artifact=artifact,
    )


_ARTIFACT_DIFF_FIELDS = ["name", "location", "tools", "instructions", "significance", "tags"]


def _norm_artifact_snap(snap, is_live=False):
    """Normalise a snapshot (or live artifact dict) into comparable scalar values."""
    result = {}
    for f in _ARTIFACT_DIFF_FIELDS:
        if f == "tags":
            raw = snap.get("tags", [])
            if is_live:
                result["tags"] = ", ".join(sorted(t["name"] for t in raw))
            else:
                result["tags"] = (
                    ", ".join(sorted(raw)) if isinstance(raw, list) else (raw or "")
                )
        else:
            result[f] = snap.get(f, "") or ""
    return result


@artifacts_bp.route("/artifact/<int:artifact_id>/history")
@login_required
def artifact_history(artifact_id):
    artifact = artifact_model.get_by_id(artifact_id)
    if not artifact:
        abort(404)
    history = history_model.get_history_for_artifact(artifact_id)

    versions = []
    for i, h in enumerate(history):
        before_norm = _norm_artifact_snap(h["snapshot"])
        if i == 0:
            after_norm = _norm_artifact_snap(artifact, is_live=True)
        else:
            after_norm = _norm_artifact_snap(history[i - 1]["snapshot"])

        action = "Created" if not h["snapshot"] else "Edited"
        diff = [
            {"field": f, "before": before_norm[f], "after": after_norm[f]}
            for f in _ARTIFACT_DIFF_FIELDS
            if before_norm[f] != after_norm[f]
        ]
        versions.append({"entry": h, "action": action, "diff": diff})

    return render_template(
        "artifact_history.html", artifact=artifact, versions=versions
    )


@artifacts_bp.route("/artifact/<int:artifact_id>/delete", methods=["GET", "POST"])
@login_required
def delete_artifact(artifact_id):
    artifact = artifact_model.get_by_id(artifact_id)
    if not artifact:
        abort(404)

    if request.method == "POST":
        artifact_model.delete(artifact_id)
        flash("Artifact deleted.", "success")
        return redirect(url_for("artifacts.index"))

    return render_template("confirm_delete.html", artifact=artifact)


# ── CSV Export / Import ───────────────────────────────────────────────────────

_CSV_HEADERS = [
    "id", "name", "location", "tools", "instructions", "significance",
    "tags", "created_at", "updated_at", "created_by", "updated_by",
]
_CSV_EXAMPLE = {
    "name": "Windows Event Logs",
    "location": r"C:\Windows\System32\winevt\Logs",
    "tools": "Event Viewer, Chainsaw, Hayabusa",
    "instructions": "Collect .evtx files from the Logs directory",
    "significance": "Primary Windows logging mechanism",
    "tags": "windows; logs",
}


@artifacts_bp.route("/artifacts/export")
@login_required
def export_csv():
    if request.args.get("template"):
        return make_template_csv(_CSV_HEADERS, _CSV_EXAMPLE, "artifacts_template.csv")
    search = request.args.get("q", "").strip()
    tag_filter = request.args.get("tag", "").strip()
    artifacts = artifact_model.get_all(
        search=search or None, tag_filter=tag_filter or None
    )
    rows = []
    for a in artifacts:
        row = dict(a)
        row["tags"] = "; ".join(t["name"] for t in a["tags"])
        rows.append(row)
    return make_csv_response(_CSV_HEADERS, rows, "artifacts.csv")


@artifacts_bp.route("/artifacts/import", methods=["GET", "POST"])
@login_required
def import_csv():
    if request.method == "GET":
        return render_template(
            "csv_import.html",
            entity="Artifacts",
            import_action=url_for("artifacts.import_csv"),
            export_template_url=url_for("artifacts.export_csv", template=1),
            cancel_url=url_for("artifacts.index"),
        )
    f = request.files.get("csv_file")
    if not f or not f.filename:
        flash("No file selected.", "danger")
        return redirect(url_for("artifacts.import_csv"))
    rows, err = parse_csv_upload(f)
    if err:
        flash(err, "danger")
        return redirect(url_for("artifacts.import_csv"))
    for row in rows:
        if not row.get("name", "").strip():
            row["_error"] = "Missing required field: name"
    headers = [h for h in (rows[0].keys() if rows else _CSV_HEADERS) if not h.startswith("_")]
    valid_count = sum(1 for r in rows if not r.get("_error"))
    return render_template(
        "csv_import_preview.html",
        entity="Artifacts",
        rows=rows,
        headers=headers,
        rows_json=_json.dumps(rows),
        confirm_url=url_for("artifacts.import_csv_confirm"),
        cancel_url=url_for("artifacts.index"),
        valid_count=valid_count,
    )


@artifacts_bp.route("/artifacts/import/confirm", methods=["POST"])
@login_required
def import_csv_confirm():
    rows_json = request.form.get("rows_json", "[]")
    try:
        rows = _json.loads(rows_json)
        if not isinstance(rows, list):
            raise ValueError("Expected a list")
    except (TypeError, ValueError) as exc:
        flash(f"Invalid import data: {exc}", "danger")
        return redirect(url_for("artifacts.index"))
    editor = current_user.username
    count = 0
    for row in rows:
        if row.get("_error"):
            continue
        name = _sanitize(row.get("name", ""))
        if not name:
            continue
        tags = [_sanitize(t.strip()) for t in row.get("tags", "").split(";") if t.strip()]
        artifact_id = artifact_model.create(
            name=name,
            location=_sanitize(row.get("location", "")),
            tools=_sanitize(row.get("tools", "")),
            instructions=_sanitize(row.get("instructions", "")),
            significance=_sanitize(row.get("significance", "")),
            created_by=editor,
            tags=tags,
        )
        history_model.insert_history(
            artifact_id=artifact_id,
            editor_name=editor,
            change_summary="Imported via CSV",
            artifact_snapshot={},
        )
        count += 1
    flash(f"Imported {count} artifact(s).", "success" if count else "warning")
    return redirect(url_for("artifacts.index"))
