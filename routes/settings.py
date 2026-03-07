import bleach
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from models import settings as settings_model

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

_MAX_TIMEZONES = 20
_MAX_TZ_LEN = 64


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        raw = request.form.get("timezones", "")
        lines = []
        for line in raw.splitlines():
            tz = bleach.clean(line.strip(), tags=[], attributes={}, strip=True)
            if tz and len(tz) <= _MAX_TZ_LEN:
                lines.append(tz)
            if len(lines) >= _MAX_TIMEZONES:
                break
        settings_model.set_setting("timezones", "\n".join(lines))
        flash("Settings saved.", "success")
        return redirect(url_for("settings.index"))

    tz_raw = settings_model.get_setting("timezones")
    return render_template("settings.html", tz_raw=tz_raw)
