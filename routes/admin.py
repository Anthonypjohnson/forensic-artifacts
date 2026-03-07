from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from argon2 import PasswordHasher

from forms.auth_form import CreateUserForm
from models import user as user_model
from models import log as log_model
from utils.pagination import get_page_args, paginate

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    all_users = user_model.get_all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if user_model.get_by_username(username):
            flash(f"Username '{username}' is already taken.", "danger")
            return render_template("admin/create_user.html", form=form)
        hashed = ph.hash(form.password.data)
        user_model.create_user(username, hashed, is_admin=form.is_admin.data)
        flash(f"User '{username}' created.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/create_user.html", form=form)


@admin_bp.route("/users/<int:user_id>/disable", methods=["POST"])
@login_required
@admin_required
def disable_user(user_id):
    if user_id == current_user.id:
        flash("You cannot disable your own account.", "warning")
        return redirect(url_for("admin.users"))
    user_model.set_active(user_id, False)
    flash("Account disabled.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/enable", methods=["POST"])
@login_required
@admin_required
def enable_user(user_id):
    user_model.set_active(user_id, True)
    flash("Account enabled.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/log")
@login_required
@admin_required
def activity_log():
    editor = request.args.get("editor", "").strip() or None
    kind = request.args.get("kind", "").strip() or None
    if kind not in (None, "artifact", "ioc", "event", "task"):
        kind = None
    page, per_page = get_page_args(request)
    all_entries = log_model.get_activity_log(limit=10000, editor=editor, kind=kind)
    pag = paginate(all_entries, page, per_page)
    return render_template(
        "admin/log.html",
        entries=pag["items"],
        pagination=pag,
        editor=editor or "",
        kind=kind or "",
    )


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@admin_required
def reset_password(user_id):
    import secrets
    new_pw = secrets.token_urlsafe(16)
    hashed = ph.hash(new_pw)
    user_model.update_password(user_id, hashed)
    target = user_model.get_by_id(user_id)
    flash(
        f"Password for '{target.username}' reset to: {new_pw}  — share this securely.",
        "warning",
    )
    return redirect(url_for("admin.users"))
