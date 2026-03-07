import logging
from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from forms.auth_form import LoginForm, ChangePasswordForm
from models import user as user_model

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)
ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("artifacts.index"))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data
        remote_ip = request.remote_addr

        user = user_model.get_by_username(username)

        if user is None:
            logger.info("Failed login: unknown username=%r ip=%s", username, remote_ip)
            flash("Invalid credentials.", "danger")
            return render_template("auth/login.html", form=form)

        # Check and clear expired lockout
        user_model.clear_lockout_if_expired(user.id)
        # Reload after potential state change
        user = user_model.get_by_username(username)

        if user.is_locked():
            logger.info("Failed login: account locked username=%r ip=%s", username, remote_ip)
            flash("Account is temporarily locked. Please try again later.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_active:
            logger.info("Failed login: account disabled username=%r ip=%s", username, remote_ip)
            flash("Invalid credentials.", "danger")
            return render_template("auth/login.html", form=form)

        try:
            ph.verify(user.password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            user_model.record_failed_attempt(user.id)
            logger.info("Failed login: bad password username=%r ip=%s", username, remote_ip)
            flash("Invalid credentials.", "danger")
            return render_template("auth/login.html", form=form)

        # Rehash if parameters changed
        if ph.check_needs_rehash(user.password_hash):
            user_model.update_password(user.id, ph.hash(password))

        user_model.record_successful_login(user.id)
        login_user(user, remember=False)
        logger.info("Successful login: username=%r ip=%s", username, remote_ip)

        next_page = request.args.get("next")
        # Guard against open redirect: only allow relative paths (no scheme, no netloc)
        if next_page:
            parsed = urlparse(next_page)
            if not parsed.scheme and not parsed.netloc:
                return redirect(next_page)
        return redirect(url_for("artifacts.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            ph.verify(current_user.password_hash, form.current_password.data)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            flash("Current password is incorrect.", "danger")
            return render_template("auth/change_password.html", form=form)

        new_hash = ph.hash(form.new_password.data)
        user_model.update_password(current_user.id, new_hash)
        flash("Password changed successfully.", "success")
        return redirect(url_for("artifacts.index"))

    return render_template("auth/change_password.html", form=form)
