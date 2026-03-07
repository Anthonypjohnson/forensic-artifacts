import json as _json

import bleach
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from forms.task_form import TaskForm
from models import task as task_model
from utils.csv_io import make_csv_response, make_template_csv, parse_csv_upload
from utils.pagination import get_page_args, paginate

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")

_ALLOWED_TAGS = []
_ALLOWED_ATTRS = {}
_TEXT_FIELDS = ['title', 'assignee', 'description', 'notes']


def _sanitize(text):
    return bleach.clean(text or '', tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


def _sanitize_form(form):
    fields = {}
    for f in _TEXT_FIELDS:
        fields[f] = _sanitize(getattr(form, f).data or '')
    fields['status'] = form.status.data
    fields['priority'] = form.priority.data
    return fields


@tasks_bp.route("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    assignee_filter = request.args.get("assignee", "").strip()
    priority_filter = request.args.get("priority", "").strip()
    page, per_page = get_page_args(request)

    all_tasks = task_model.get_all(
        search=search or None,
        status_filter=status_filter or None,
        assignee_filter=assignee_filter or None,
        priority_filter=priority_filter or None,
    )
    pag = paginate(all_tasks, page, per_page)
    return render_template(
        "task_index.html",
        tasks=pag["items"],
        pagination=pag,
        search=search,
        status_filter=status_filter,
        assignee_filter=assignee_filter,
        priority_filter=priority_filter,
    )


@tasks_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_task():
    form = TaskForm()
    if form.validate_on_submit():
        fields = _sanitize_form(form)
        task_id = task_model.create(fields, created_by=current_user.username)
        task_model.insert_history(task_id, current_user.username, "created", {})
        flash("Task created.", "success")
        return redirect(url_for("tasks.detail", task_id=task_id))
    return render_template("task_form.html", form=form, title="New Task", task=None)


@tasks_bp.route("/<int:task_id>")
@login_required
def detail(task_id):
    task = task_model.get_by_id(task_id)
    if not task:
        abort(404)
    return render_template("task_detail.html", task=task)


@tasks_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = task_model.get_by_id(task_id)
    if not task:
        abort(404)

    form = TaskForm()
    if form.validate_on_submit():
        fields = _sanitize_form(form)
        snapshot = {k: task.get(k) for k in task_model.TASK_FIELDS}
        task_model.update(task_id, fields, updated_by=current_user.username)
        task_model.insert_history(task_id, current_user.username, "edited", snapshot)
        flash("Task updated.", "success")
        return redirect(url_for("tasks.detail", task_id=task_id))

    if request.method == "GET":
        form.title.data = task.get('title', '')
        form.status.data = task.get('status', 'Open')
        form.priority.data = task.get('priority', 'Medium')
        form.assignee.data = task.get('assignee', '')
        form.description.data = task.get('description', '')
        form.notes.data = task.get('notes', '')

    return render_template("task_form.html", form=form, title=f"Edit Task #{task_id}", task=task)


@tasks_bp.route("/<int:task_id>/delete", methods=["GET", "POST"])
@login_required
def delete_task(task_id):
    task = task_model.get_by_id(task_id)
    if not task:
        abort(404)

    if request.method == "POST":
        task_model.delete(task_id)
        flash("Task deleted.", "success")
        return redirect(url_for("tasks.index"))

    return render_template("task_confirm_delete.html", task=task)


@tasks_bp.route("/<int:task_id>/claim", methods=["POST"])
@login_required
def claim_task(task_id):
    task = task_model.get_by_id(task_id)
    if not task:
        abort(404)

    action = request.form.get("action", "claim")
    task_model.claim(task_id, current_user.username, release=(action == "release"))

    if action == "release":
        flash("Task released.", "info")
    else:
        flash("Task claimed.", "success")
    return redirect(url_for("tasks.detail", task_id=task_id))


# ── CSV Export / Import ───────────────────────────────────────────────────────

_CSV_HEADERS = [
    "id", "title", "status", "priority", "assignee",
    "description", "notes", "created_at", "updated_at", "created_by", "updated_by",
]
_CSV_EXAMPLE = {
    "title": "Investigate phishing email",
    "status": "Open",
    "priority": "High",
    "assignee": "analyst1",
    "description": "Review the suspicious email and attached payload",
    "notes": "",
}
_VALID_STATUSES = {"Open", "In Progress", "Blocked", "Done"}
_VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}


@tasks_bp.route("/export")
@login_required
def export_csv():
    if request.args.get("template"):
        return make_template_csv(_CSV_HEADERS, _CSV_EXAMPLE, "tasks_template.csv")
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    assignee_filter = request.args.get("assignee", "").strip()
    priority_filter = request.args.get("priority", "").strip()
    tasks = task_model.get_all(
        search=search or None,
        status_filter=status_filter or None,
        assignee_filter=assignee_filter or None,
        priority_filter=priority_filter or None,
    )
    return make_csv_response(_CSV_HEADERS, tasks, "tasks.csv")


@tasks_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_csv():
    if request.method == "GET":
        return render_template(
            "csv_import.html",
            entity="Tasks",
            import_action=url_for("tasks.import_csv"),
            export_template_url=url_for("tasks.export_csv", template=1),
            cancel_url=url_for("tasks.index"),
        )
    f = request.files.get("csv_file")
    if not f or not f.filename:
        flash("No file selected.", "danger")
        return redirect(url_for("tasks.import_csv"))
    rows, err = parse_csv_upload(f)
    if err:
        flash(err, "danger")
        return redirect(url_for("tasks.import_csv"))
    for row in rows:
        if not row.get("title", "").strip():
            row["_error"] = "Missing required field: title"
    headers = [h for h in (rows[0].keys() if rows else _CSV_HEADERS) if not h.startswith("_")]
    valid_count = sum(1 for r in rows if not r.get("_error"))
    return render_template(
        "csv_import_preview.html",
        entity="Tasks",
        rows=rows,
        headers=headers,
        rows_json=_json.dumps(rows),
        confirm_url=url_for("tasks.import_csv_confirm"),
        cancel_url=url_for("tasks.index"),
        valid_count=valid_count,
    )


@tasks_bp.route("/import/confirm", methods=["POST"])
@login_required
def import_csv_confirm():
    rows_json = request.form.get("rows_json", "[]")
    try:
        rows = _json.loads(rows_json)
        if not isinstance(rows, list):
            raise ValueError("Expected a list")
    except (TypeError, ValueError) as exc:
        flash(f"Invalid import data: {exc}", "danger")
        return redirect(url_for("tasks.index"))
    editor = current_user.username
    count = 0
    for row in rows:
        if not isinstance(row, dict) or row.get("_error"):
            continue
        title = _sanitize(row.get("title", ""))
        if not title:
            continue
        status = row.get("status", "Open")
        priority = row.get("priority", "Medium")
        fields = {
            "title": title,
            "status": status if status in _VALID_STATUSES else "Open",
            "priority": priority if priority in _VALID_PRIORITIES else "Medium",
            "assignee": _sanitize(row.get("assignee", "")) or None,
            "description": _sanitize(row.get("description", "")),
            "notes": _sanitize(row.get("notes", "")),
        }
        task_id = task_model.create(fields, created_by=editor)
        task_model.insert_history(task_id, editor, "created", {})
        count += 1
    flash(f"Imported {count} task(s).", "success" if count else "warning")
    return redirect(url_for("tasks.index"))
