import bleach
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from forms.ioc_form import IocForm
from models import ioc as ioc_model

iocs_bp = Blueprint("iocs", __name__, url_prefix="/iocs")

_ALLOWED_TAGS = []
_ALLOWED_ATTRS = {}

_IOC_TEXT_FIELDS = [
    'case_name', 'hostname', 'ip_address', 'domain', 'url',
    'hash_value', 'filename', 'file_path', 'registry_key',
    'command_line', 'email', 'user_account', 'notes',
]


def _sanitize(text):
    return bleach.clean(text, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


def _sanitize_form(form):
    fields = {}
    for f in _IOC_TEXT_FIELDS:
        fields[f] = _sanitize(getattr(form, f).data or '')
    fields['severity'] = form.severity.data
    fields['hash_type'] = form.hash_type.data
    fields['tags'] = [_sanitize(t) for t in form.tags.data.split(',') if t.strip()]
    fields['editor_name'] = _sanitize(form.editor_name.data)
    fields['change_note'] = _sanitize(form.change_note.data)
    return fields


@iocs_bp.route("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    case_filter = request.args.get("case", "").strip()
    tag_filter = request.args.get("tag", "").strip()
    iocs = ioc_model.get_all(
        search=search or None,
        case_filter=case_filter or None,
        tag_filter=tag_filter or None,
    )
    all_cases = ioc_model.get_distinct_cases()
    all_tags = ioc_model.get_all_tags_with_counts()
    return render_template(
        "ioc_index.html",
        iocs=iocs,
        all_cases=all_cases,
        all_tags=all_tags,
        search=search,
        case_filter=case_filter,
        tag_filter=tag_filter,
    )


@iocs_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_ioc():
    form = IocForm()
    if form.validate_on_submit():
        fields = _sanitize_form(form)
        editor = current_user.username
        ioc_id = ioc_model.create(
            fields_dict=fields,
            created_by=editor,
            tag_names=fields['tags'],
        )
        ioc_model.insert_history(
            ioc_id=ioc_id,
            editor_name=editor,
            change_summary=fields['change_note'],
            snapshot_dict={},
        )
        flash("IOC created.", "success")
        return redirect(url_for("iocs.detail", ioc_id=ioc_id))
    form.editor_name.data = current_user.username
    return render_template("ioc_form.html", form=form, title="New IOC")


@iocs_bp.route("/<int:ioc_id>")
@login_required
def detail(ioc_id):
    ioc = ioc_model.get_by_id(ioc_id)
    if not ioc:
        abort(404)
    history = ioc_model.get_history_for_ioc(ioc_id)
    return render_template("ioc_detail.html", ioc=ioc, history=history)


@iocs_bp.route("/<int:ioc_id>/edit", methods=["GET", "POST"])
@login_required
def edit_ioc(ioc_id):
    ioc = ioc_model.get_by_id(ioc_id)
    if not ioc:
        abort(404)

    form = IocForm()

    if form.validate_on_submit():
        fields = _sanitize_form(form)
        editor = current_user.username
        # Snapshot before changes
        snapshot = {f: ioc[f] for f in ioc_model.IOC_FIELDS}
        snapshot['tags'] = [t['name'] for t in ioc['tags']]

        ioc_model.update(
            ioc_id=ioc_id,
            fields_dict=fields,
            updated_by=editor,
            tag_names=fields['tags'],
        )
        ioc_model.insert_history(
            ioc_id=ioc_id,
            editor_name=editor,
            change_summary=fields['change_note'],
            snapshot_dict=snapshot,
        )
        flash("IOC updated.", "success")
        return redirect(url_for("iocs.detail", ioc_id=ioc_id))

    if request.method == "GET":
        for f in ioc_model.IOC_FIELDS:
            if hasattr(form, f):
                getattr(form, f).data = ioc[f]
        form.tags.data = ", ".join(t['name'] for t in ioc['tags'])

    form.editor_name.data = current_user.username
    return render_template(
        "ioc_form.html",
        form=form,
        title=f"Edit IOC #{ioc_id}",
        ioc=ioc,
    )


_IOC_DIFF_FIELDS = ioc_model.IOC_FIELDS + ["tags"]


def _norm_ioc_snap(snap, is_live=False):
    """Normalise a snapshot (or live ioc dict) into comparable scalar values."""
    result = {}
    for f in _IOC_DIFF_FIELDS:
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


@iocs_bp.route("/<int:ioc_id>/history")
@login_required
def ioc_history(ioc_id):
    ioc = ioc_model.get_by_id(ioc_id)
    if not ioc:
        abort(404)
    history = ioc_model.get_history_for_ioc(ioc_id)

    versions = []
    for i, h in enumerate(history):
        before_norm = _norm_ioc_snap(h["snapshot"])
        if i == 0:
            after_norm = _norm_ioc_snap(ioc, is_live=True)
        else:
            after_norm = _norm_ioc_snap(history[i - 1]["snapshot"])

        action = "Created" if not h["snapshot"] else "Edited"
        diff = [
            {"field": f, "before": before_norm[f], "after": after_norm[f]}
            for f in _IOC_DIFF_FIELDS
            if before_norm[f] != after_norm[f]
        ]
        versions.append({"entry": h, "action": action, "diff": diff})

    return render_template("ioc_history.html", ioc=ioc, versions=versions)


@iocs_bp.route("/<int:ioc_id>/delete", methods=["GET", "POST"])
@login_required
def delete_ioc(ioc_id):
    ioc = ioc_model.get_by_id(ioc_id)
    if not ioc:
        abort(404)

    if request.method == "POST":
        ioc_model.delete(ioc_id)
        flash("IOC deleted.", "success")
        return redirect(url_for("iocs.index"))

    return render_template("ioc_confirm_delete.html", ioc=ioc)
