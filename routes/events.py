import json as _json
import os
import uuid

import bleach
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from forms.event_form import EventForm
from models import event as event_model
from models import task as task_model
from utils.csv_io import make_csv_response, make_template_csv, parse_csv_upload

events_bp = Blueprint("events", __name__, url_prefix="/events")

_UPLOAD_DIR = os.path.join("static", "uploads", "events")
_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
_ALLOWED_TAGS = []
_ALLOWED_ATTRS = {}

_EVENT_TEXT_FIELDS = [
    'event_category', 'system', 'account', 'event_datetime',
    'high_level_source', 'detailed_source', 'notes', 'task_id',
]
# linked_task_id is handled separately (int/None)


def _sanitize(text):
    return bleach.clean(text, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


def _allowed_ext(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in _ALLOWED_EXTENSIONS


def _save_screenshot(file_storage):
    """Validate and save uploaded screenshot. Returns stored filename or None."""
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    if not _allowed_ext(filename):
        return None
    ext = filename.rsplit('.', 1)[1].lower()

    # MIME sniff — best-effort, falls back to extension check only
    try:
        import imghdr
        file_storage.seek(0)
        detected = imghdr.what(file_storage)
        file_storage.seek(0)
        _IMGHDR_EXTS = {'png', 'jpeg', 'gif', 'webp', 'jpg'}
        if detected and detected not in _IMGHDR_EXTS and detected != 'jpeg':
            return None
    except Exception:
        pass

    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(_UPLOAD_DIR, stored_name))
    return stored_name


def _delete_screenshot(screenshot_path):
    if screenshot_path:
        try:
            os.remove(os.path.join(_UPLOAD_DIR, screenshot_path))
        except OSError:
            pass


def _sanitize_form(form):
    fields = {}
    for f in _EVENT_TEXT_FIELDS:
        fields[f] = _sanitize(getattr(form, f).data or '')
    raw_ioc = form.ioc_id.data
    fields['ioc_id'] = int(raw_ioc) if raw_ioc and raw_ioc.isdigit() else None
    raw_task = form.linked_task_id.data
    fields['linked_task_id'] = int(raw_task) if raw_task and raw_task.isdigit() else None
    fields['show_on_timeline'] = bool(form.show_on_timeline.data)
    fields['tags'] = [_sanitize(t) for t in form.tags.data.split(',') if t.strip()]
    fields['editor_name'] = _sanitize(form.editor_name.data)
    fields['change_note'] = _sanitize(form.change_note.data)
    return fields


def _populate_ioc_choices(form):
    iocs = event_model.get_all_iocs_brief()
    form.ioc_id.choices = [('', '— none —')] + [
        (str(i['id']), i['label']) for i in iocs
    ]
    tasks = task_model.get_all_tasks_brief()
    form.linked_task_id.choices = [('', '— none —')] + [
        (str(t['id']), f"#{t['id']} — {t['title'][:60]} [{t['status']}]") for t in tasks
    ]


# ── Routes ───────────────────────────────────────────────────────────────────

@events_bp.route("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    ioc_filter = request.args.get("ioc", "").strip()
    system_filter = request.args.get("system", "").strip()
    account_filter = request.args.get("account", "").strip()
    tag_filter = request.args.get("tag", "").strip()
    source_filter = request.args.get("source", "").strip()

    events = event_model.get_all(
        search=search or None,
        ioc_filter=int(ioc_filter) if ioc_filter.isdigit() else None,
        system_filter=system_filter or None,
        account_filter=account_filter or None,
        source_filter=source_filter or None,
        tag_filter=tag_filter or None,
    )
    all_iocs = event_model.get_all_iocs_brief()
    all_tags = event_model.get_all_event_tags_with_counts()
    return render_template(
        "event_index.html",
        events=events,
        all_iocs=all_iocs,
        all_tags=all_tags,
        search=search,
        ioc_filter=ioc_filter,
        system_filter=system_filter,
        account_filter=account_filter,
        tag_filter=tag_filter,
        source_filter=source_filter,
    )


@events_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_event():
    form = EventForm()
    _populate_ioc_choices(form)

    if form.validate_on_submit():
        fields = _sanitize_form(form)
        screenshot_name = _save_screenshot(request.files.get('screenshot'))
        if screenshot_name:
            fields['screenshot_path'] = screenshot_name

        editor = current_user.username
        event_id = event_model.create(
            fields_dict=fields,
            created_by=editor,
            tag_names=fields['tags'],
        )
        event_model.insert_history(
            event_id=event_id,
            editor_name=editor,
            change_summary=fields['change_note'],
            snapshot_dict={},
        )
        flash("Event created.", "success")
        return redirect(url_for("events.detail", event_id=event_id))

    form.editor_name.data = current_user.username
    return render_template("event_form.html", form=form, title="New Event", event=None)


@events_bp.route("/<int:event_id>")
@login_required
def detail(event_id):
    event = event_model.get_by_id(event_id)
    if not event:
        abort(404)
    history = event_model.get_history_for_event(event_id)
    return render_template("event_detail.html", event=event, history=history)


@events_bp.route("/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
def edit_event(event_id):
    event = event_model.get_by_id(event_id)
    if not event:
        abort(404)

    form = EventForm()
    _populate_ioc_choices(form)

    if form.validate_on_submit():
        fields = _sanitize_form(form)
        editor = current_user.username

        # Snapshot before update
        snapshot = {f: event.get(f, '') for f in event_model.EVENT_FIELDS}
        snapshot['tags'] = [t['name'] for t in event['tags']]

        # Screenshot handling
        old_path = event.get('screenshot_path', '')
        remove_shot = request.form.get('remove_screenshot')
        new_file = request.files.get('screenshot')
        new_name = _save_screenshot(new_file)

        if new_name:
            _delete_screenshot(old_path)
            fields['screenshot_path'] = new_name
        elif remove_shot:
            _delete_screenshot(old_path)
            fields['screenshot_path'] = ''
        else:
            fields['screenshot_path'] = old_path

        event_model.update(
            event_id=event_id,
            fields_dict=fields,
            updated_by=editor,
            tag_names=fields['tags'],
        )
        event_model.insert_history(
            event_id=event_id,
            editor_name=editor,
            change_summary=fields['change_note'],
            snapshot_dict=snapshot,
        )
        flash("Event updated.", "success")
        return redirect(url_for("events.detail", event_id=event_id))

    if request.method == "GET":
        form.ioc_id.data = str(event['ioc_id']) if event.get('ioc_id') else ''
        form.show_on_timeline.data = bool(event.get('show_on_timeline', 1))
        form.event_category.data = event.get('event_category', '')
        form.system.data = event.get('system', '')
        form.account.data = event.get('account', '')
        form.event_datetime.data = event.get('event_datetime', '')
        form.high_level_source.data = event.get('high_level_source', '')
        form.detailed_source.data = event.get('detailed_source', '')
        form.notes.data = event.get('notes', '')
        form.task_id.data = event.get('task_id', '')
        form.linked_task_id.data = str(event['linked_task_id']) if event.get('linked_task_id') else ''
        form.tags.data = ", ".join(t['name'] for t in event['tags'])

    form.editor_name.data = current_user.username
    return render_template(
        "event_form.html",
        form=form,
        title=f"Edit Event #{event_id}",
        event=event,
    )


@events_bp.route("/<int:event_id>/history")
@login_required
def event_history(event_id):
    event = event_model.get_by_id(event_id)
    if not event:
        abort(404)
    history = event_model.get_history_for_event(event_id)

    _DIFF_FIELDS = [f for f in event_model.EVENT_FIELDS if f != 'screenshot_path'] + ['tags']

    def _norm(snap, is_live=False):
        result = {}
        for f in _DIFF_FIELDS:
            if f == 'tags':
                raw = snap.get('tags', [])
                if is_live:
                    result['tags'] = ", ".join(sorted(t['name'] for t in raw))
                else:
                    result['tags'] = (
                        ", ".join(sorted(raw)) if isinstance(raw, list) else (raw or "")
                    )
            else:
                val = snap.get(f, '')
                result[f] = str(val) if val is not None else ''
        return result

    versions = []
    for i, h in enumerate(history):
        before_norm = _norm(h["snapshot"])
        after_norm = _norm(event, is_live=True) if i == 0 else _norm(history[i - 1]["snapshot"])
        action = "Created" if not h["snapshot"] else "Edited"
        diff = [
            {"field": f, "before": before_norm[f], "after": after_norm[f]}
            for f in _DIFF_FIELDS
            if before_norm[f] != after_norm[f]
        ]
        versions.append({"entry": h, "action": action, "diff": diff})

    return render_template("event_history.html", event=event, versions=versions)


@events_bp.route("/<int:event_id>/delete", methods=["GET", "POST"])
@login_required
def delete_event(event_id):
    event = event_model.get_by_id(event_id)
    if not event:
        abort(404)

    if request.method == "POST":
        event_model.delete(event_id)
        flash("Event deleted.", "success")
        return redirect(url_for("events.index"))

    return render_template("event_confirm_delete.html", event=event)


# ── CSV Export / Import ───────────────────────────────────────────────────────

_CSV_HEADERS = [
    "id", "event_datetime", "event_category", "system", "account",
    "high_level_source", "detailed_source", "notes", "task_id",
    "ioc_id", "linked_task_id", "show_on_timeline",
    "tags", "created_at", "updated_at", "created_by", "updated_by",
]
_CSV_EXAMPLE = {
    "event_datetime": "2026-01-01T12:00:00",
    "event_category": "Authentication",
    "system": "WS01.corp.local",
    "account": "jdoe",
    "high_level_source": "Windows Security Log",
    "detailed_source": "Event ID 4624",
    "notes": "Successful logon",
    "show_on_timeline": "1",
    "tags": "auth; windows",
}


@events_bp.route("/export")
@login_required
def export_csv():
    if request.args.get("template"):
        return make_template_csv(_CSV_HEADERS, _CSV_EXAMPLE, "events_template.csv")
    search = request.args.get("q", "").strip()
    ioc_filter = request.args.get("ioc", "").strip()
    system_filter = request.args.get("system", "").strip()
    account_filter = request.args.get("account", "").strip()
    tag_filter = request.args.get("tag", "").strip()
    source_filter = request.args.get("source", "").strip()
    events = event_model.get_all(
        search=search or None,
        ioc_filter=int(ioc_filter) if ioc_filter.isdigit() else None,
        system_filter=system_filter or None,
        account_filter=account_filter or None,
        source_filter=source_filter or None,
        tag_filter=tag_filter or None,
    )
    rows = []
    for ev in events:
        row = dict(ev)
        row["tags"] = "; ".join(t["name"] for t in ev["tags"])
        rows.append(row)
    return make_csv_response(_CSV_HEADERS, rows, "events.csv")


@events_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_csv():
    if request.method == "GET":
        return render_template(
            "csv_import.html",
            entity="Events",
            import_action=url_for("events.import_csv"),
            export_template_url=url_for("events.export_csv", template=1),
            cancel_url=url_for("events.index"),
        )
    f = request.files.get("csv_file")
    if not f or not f.filename:
        flash("No file selected.", "danger")
        return redirect(url_for("events.import_csv"))
    rows, err = parse_csv_upload(f)
    if err:
        flash(err, "danger")
        return redirect(url_for("events.import_csv"))
    # No required fields for events
    headers = [h for h in (rows[0].keys() if rows else _CSV_HEADERS) if not h.startswith("_")]
    valid_count = sum(1 for r in rows if not r.get("_error"))
    return render_template(
        "csv_import_preview.html",
        entity="Events",
        rows=rows,
        headers=headers,
        rows_json=_json.dumps(rows),
        confirm_url=url_for("events.import_csv_confirm"),
        cancel_url=url_for("events.index"),
        valid_count=valid_count,
    )


@events_bp.route("/import/confirm", methods=["POST"])
@login_required
def import_csv_confirm():
    rows_json = request.form.get("rows_json", "[]")
    try:
        rows = _json.loads(rows_json)
        if not isinstance(rows, list):
            raise ValueError("Expected a list")
    except (TypeError, ValueError) as exc:
        flash(f"Invalid import data: {exc}", "danger")
        return redirect(url_for("events.index"))
    editor = current_user.username
    count = 0
    for row in rows:
        if not isinstance(row, dict) or row.get("_error"):
            continue
        tags = [_sanitize(t.strip()) for t in row.get("tags", "").split(";") if t.strip()]
        # Resolve integer FK fields; silently null if not a valid integer
        raw_ioc = row.get("ioc_id", "")
        raw_linked = row.get("linked_task_id", "")
        sol_raw = row.get("show_on_timeline", "1")
        fields = {
            "event_datetime": _sanitize(row.get("event_datetime", "")),
            "event_category": _sanitize(row.get("event_category", "")),
            "system": _sanitize(row.get("system", "")),
            "account": _sanitize(row.get("account", "")),
            "high_level_source": _sanitize(row.get("high_level_source", "")),
            "detailed_source": _sanitize(row.get("detailed_source", "")),
            "notes": _sanitize(row.get("notes", "")),
            "task_id": _sanitize(row.get("task_id", "")),
            "ioc_id": int(raw_ioc) if raw_ioc and str(raw_ioc).isdigit() else None,
            "linked_task_id": int(raw_linked) if raw_linked and str(raw_linked).isdigit() else None,
            "show_on_timeline": sol_raw.lower() not in ("0", "false", "no", ""),
        }
        event_id = event_model.create(
            fields_dict=fields,
            created_by=editor,
            tag_names=tags,
        )
        event_model.insert_history(
            event_id=event_id,
            editor_name=editor,
            change_summary="Imported via CSV",
            snapshot_dict={},
        )
        count += 1
    flash(f"Imported {count} event(s).", "success" if count else "warning")
    return redirect(url_for("events.index"))
