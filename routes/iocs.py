import json as _json

import bleach
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from forms.ioc_form import IocForm
from models import ioc as ioc_model
from models import event as event_model
from utils import stix_parser
from utils.csv_io import make_csv_response, make_template_csv, parse_csv_upload

iocs_bp = Blueprint("iocs", __name__, url_prefix="/iocs")

_MAX_IMPORT_BYTES = 5 * 1024 * 1024
_VALID_SEVERITIES  = {'Low', 'Medium', 'High', 'Critical'}
_VALID_HASH_TYPES  = {'', 'MD5', 'SHA1', 'SHA256', 'SHA512', 'SSDEEP'}
_VALID_MITRE       = {
    'Reconnaissance', 'Resource Development', 'Initial Access', 'Execution',
    'Persistence', 'Privilege Escalation', 'Defense Evasion', 'Credential Access',
    'Discovery', 'Lateral Movement', 'Collection', 'Command and Control',
    'Exfiltration', 'Impact',
}
_VALID_PROTOCOLS   = {
    '', 'TCP', 'UDP', 'ICMP', 'HTTP', 'HTTPS', 'DNS',
    'SMTP', 'FTP', 'SSH', 'SMB', 'RDP', 'TLS', 'Other',
}

_ALLOWED_TAGS = []
_ALLOWED_ATTRS = {}

_IOC_TEXT_FIELDS = [
    'category', 'hostname', 'ip_address', 'domain', 'url',
    'hash_value', 'filename', 'file_path', 'registry_key',
    'command_line', 'email', 'user_account', 'notes',
    'user_agent', 'detection_rule', 'network_port',
]


def _sanitize(text):
    return bleach.clean(text, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


def _sanitize_raw_fields(d: dict) -> dict:
    """Sanitize a raw IOC dict (e.g. from STIX parser) for storage."""
    fields = {}
    for f in _IOC_TEXT_FIELDS:
        fields[f] = _sanitize(str(d.get(f, '') or ''))
    sev = d.get('severity', 'Medium')
    fields['severity'] = sev if sev in _VALID_SEVERITIES else 'Medium'
    ht = d.get('hash_type', '')
    fields['hash_type'] = ht if ht in _VALID_HASH_TYPES else ''
    mc = d.get('mitre_category', '')
    fields['mitre_category'] = mc if mc in _VALID_MITRE else ''
    np_ = d.get('network_protocol', '')
    fields['network_protocol'] = np_ if np_ in _VALID_PROTOCOLS else ''
    return fields


def _sanitize_form(form):
    fields = {}
    for f in _IOC_TEXT_FIELDS:
        fields[f] = _sanitize(getattr(form, f).data or '')
    fields['severity'] = form.severity.data
    fields['hash_type'] = form.hash_type.data
    fields['mitre_category'] = form.mitre_category.data
    fields['network_protocol'] = form.network_protocol.data
    fields['tags'] = [_sanitize(t) for t in form.tags.data.split(',') if t.strip()]
    fields['editor_name'] = _sanitize(form.editor_name.data)
    fields['change_note'] = _sanitize(form.change_note.data)
    return fields


@iocs_bp.route("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "").strip()
    tag_filter = request.args.get("tag", "").strip()
    iocs = ioc_model.get_all(
        search=search or None,
        category_filter=category_filter or None,
        tag_filter=tag_filter or None,
    )
    all_categories = ioc_model.get_distinct_categories()
    all_tags = ioc_model.get_all_tags_with_counts()
    return render_template(
        "ioc_index.html",
        iocs=iocs,
        all_categories=all_categories,
        all_tags=all_tags,
        search=search,
        category_filter=category_filter,
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


@iocs_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_stix():
    if request.method == "GET":
        return render_template("ioc_import.html")

    f = request.files.get("stix_file")
    if not f or not f.filename:
        flash("No file selected.", "danger")
        return redirect(url_for("iocs.import_stix"))

    content = f.read(_MAX_IMPORT_BYTES + 1)
    if not content:
        flash("Uploaded file is empty.", "danger")
        return redirect(url_for("iocs.import_stix"))
    if len(content) > _MAX_IMPORT_BYTES:
        flash("File exceeds the 5 MB size limit.", "danger")
        return redirect(url_for("iocs.import_stix"))

    try:
        parsed = stix_parser.parse_stix(content, f.filename)
    except ValueError as exc:
        flash(f"Parse error: {exc}", "danger")
        return redirect(url_for("iocs.import_stix"))

    if not parsed:
        flash("No indicators found in the file.", "warning")
        return redirect(url_for("iocs.import_stix"))

    preview = []
    for ioc in parsed:
        clean = {**_sanitize_raw_fields(ioc),
                 '_tags': [_sanitize(t) for t in ioc.get('_tags', [])]}
        _, clean['_primary'] = ioc_model.get_primary_indicator(clean)
        preview.append(clean)

    source = bleach.clean(f.filename)
    return render_template(
        "ioc_import_preview.html",
        iocs=preview,
        import_json=_json.dumps(preview),
        source=source,
    )


@iocs_bp.route("/import/confirm", methods=["POST"])
@login_required
def import_stix_confirm():
    import_data = request.form.get("import_data", "")
    try:
        raw_iocs = _json.loads(import_data)
        if not isinstance(raw_iocs, list):
            raise ValueError("Expected a list")
    except (TypeError, ValueError) as exc:
        flash(f"Invalid import data: {exc}", "danger")
        return redirect(url_for("iocs.index"))

    editor = current_user.username
    change_note = _sanitize(request.form.get("change_note", "Imported from STIX"))[:512]
    extra_tags = [
        _sanitize(t.strip())
        for t in request.form.get("extra_tags", "").split(",")
        if t.strip()
    ]
    imported = 0
    for raw in raw_iocs:
        if not isinstance(raw, dict):
            continue
        per_ioc_tags = [_sanitize(t) for t in raw.get('_tags', []) if isinstance(t, str)]
        tags = list(dict.fromkeys(per_ioc_tags + extra_tags))  # merge, preserve order, dedupe
        fields = _sanitize_raw_fields(raw)
        if not any(fields.get(fi, '').strip() for fi in _IOC_TEXT_FIELDS):
            continue
        ioc_id = ioc_model.create(
            fields_dict=fields,
            created_by=editor,
            tag_names=tags,
        )
        ioc_model.insert_history(
            ioc_id=ioc_id,
            editor_name=editor,
            change_summary=change_note,
            snapshot_dict={},
        )
        imported += 1

    flash(
        f"Imported {imported} IOC(s).",
        "success" if imported else "warning",
    )
    return redirect(url_for("iocs.index"))


@iocs_bp.route("/<int:ioc_id>")
@login_required
def detail(ioc_id):
    ioc = ioc_model.get_by_id(ioc_id)
    if not ioc:
        abort(404)
    history = ioc_model.get_history_for_ioc(ioc_id)
    events = event_model.get_all(ioc_filter=ioc_id)
    return render_template("ioc_detail.html", ioc=ioc, history=history, events=events)


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


# ── CSV Export / Import ───────────────────────────────────────────────────────

_CSV_HEADERS = [
    "id", "category", "severity", "hostname", "ip_address", "domain", "url",
    "hash_value", "hash_type", "filename", "file_path", "registry_key",
    "command_line", "email", "user_account", "notes", "user_agent",
    "mitre_category", "detection_rule", "network_port", "network_protocol",
    "tags", "created_at", "updated_at", "created_by", "updated_by",
]
_CSV_EXAMPLE = {
    "category": "Network",
    "severity": "High",
    "ip_address": "192.168.1.100",
    "domain": "malicious.example.com",
    "notes": "Observed C2 communication",
    "tags": "c2; network",
}


@iocs_bp.route("/export")
@login_required
def export_csv():
    if request.args.get("template"):
        return make_template_csv(_CSV_HEADERS, _CSV_EXAMPLE, "iocs_template.csv")
    search = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "").strip()
    tag_filter = request.args.get("tag", "").strip()
    iocs = ioc_model.get_all(
        search=search or None,
        category_filter=category_filter or None,
        tag_filter=tag_filter or None,
    )
    rows = []
    for ioc in iocs:
        row = dict(ioc)
        row["tags"] = "; ".join(t["name"] for t in ioc["tags"])
        rows.append(row)
    return make_csv_response(_CSV_HEADERS, rows, "iocs.csv")


@iocs_bp.route("/import/csv", methods=["GET", "POST"])
@login_required
def import_csv():
    if request.method == "GET":
        return render_template(
            "csv_import.html",
            entity="IOCs",
            import_action=url_for("iocs.import_csv"),
            export_template_url=url_for("iocs.export_csv", template=1),
            cancel_url=url_for("iocs.index"),
        )
    f = request.files.get("csv_file")
    if not f or not f.filename:
        flash("No file selected.", "danger")
        return redirect(url_for("iocs.import_csv"))
    rows, err = parse_csv_upload(f)
    if err:
        flash(err, "danger")
        return redirect(url_for("iocs.import_csv"))
    # No required fields for IOCs (soft validation only)
    headers = [h for h in (rows[0].keys() if rows else _CSV_HEADERS) if not h.startswith("_")]
    valid_count = sum(1 for r in rows if not r.get("_error"))
    return render_template(
        "csv_import_preview.html",
        entity="IOCs",
        rows=rows,
        headers=headers,
        rows_json=_json.dumps(rows),
        confirm_url=url_for("iocs.import_csv_confirm"),
        cancel_url=url_for("iocs.index"),
        valid_count=valid_count,
    )


@iocs_bp.route("/import/csv/confirm", methods=["POST"])
@login_required
def import_csv_confirm():
    rows_json = request.form.get("rows_json", "[]")
    try:
        rows = _json.loads(rows_json)
        if not isinstance(rows, list):
            raise ValueError("Expected a list")
    except (TypeError, ValueError) as exc:
        flash(f"Invalid import data: {exc}", "danger")
        return redirect(url_for("iocs.index"))
    editor = current_user.username
    count = 0
    for row in rows:
        if not isinstance(row, dict) or row.get("_error"):
            continue
        tags = [_sanitize(t.strip()) for t in row.get("tags", "").split(";") if t.strip()]
        fields = _sanitize_raw_fields(row)
        if not any(fields.get(fi, "").strip() for fi in _IOC_TEXT_FIELDS):
            continue
        ioc_id = ioc_model.create(
            fields_dict=fields,
            created_by=editor,
            tag_names=tags,
        )
        ioc_model.insert_history(
            ioc_id=ioc_id,
            editor_name=editor,
            change_summary="Imported via CSV",
            snapshot_dict={},
        )
        count += 1
    flash(f"Imported {count} IOC(s).", "success" if count else "warning")
    return redirect(url_for("iocs.index"))
