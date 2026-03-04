import sys
import getpass
import click
from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager

from config import Config
from database import db as database
from middleware.ip_whitelist import SilentDropMiddleware


csrf = CSRFProtect()
login_manager = LoginManager()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    config_class.warn_if_default_secret()

    # Ensure DB directory exists
    app.config["DATABASE_PATH"].parent.mkdir(parents=True, exist_ok=True)

    # Extensions
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    database.init_app(app)

    # Blueprints
    from routes.auth import auth_bp
    from routes.artifacts import artifacts_bp
    from routes.api import api_bp
    from routes.admin import admin_bp
    from routes.iocs import iocs_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(artifacts_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(iocs_bp)

    # Security headers on every response
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("400.html", error=str(e)), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    # Initialize DB tables on first run (inside app context)
    with app.app_context():
        database.init_db()

    # Register CLI commands
    _register_cli(app)

    # Wrap with IP whitelist middleware
    app.wsgi_app = SilentDropMiddleware(app.wsgi_app, app.config["ALLOWED_IPS_CONF"])

    # If running behind a reverse proxy, apply ProxyFix outermost so that
    # REMOTE_ADDR is corrected from X-Forwarded-For *before* the whitelist
    # check sees it.  PROXY_COUNT must match the exact number of trusted proxies.
    proxy_count = app.config["PROXY_COUNT"]
    if proxy_count > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=proxy_count,
            x_proto=proxy_count,
            x_host=proxy_count,
            x_prefix=proxy_count,
        )

    return app


@login_manager.user_loader
def load_user(user_id):
    # Import inside function to avoid circular imports
    from models.user import get_by_id
    return get_by_id(int(user_id))


def _register_cli(app):
    @app.cli.command("create-admin")
    def create_admin():
        """Interactively create the first admin account."""
        from models.user import get_by_username, create_user
        from argon2 import PasswordHasher
        from forms.auth_form import MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH, COMMON_PASSWORDS

        click.echo("=== Create Admin Account ===")
        username = click.prompt("Username").strip()

        if get_by_username(username):
            click.echo(f"Error: user '{username}' already exists.", err=True)
            sys.exit(1)

        while True:
            password = getpass.getpass("Password (min 12 chars): ")
            if len(password) < MIN_PASSWORD_LENGTH:
                click.echo(f"Password too short (minimum {MIN_PASSWORD_LENGTH} characters).")
                continue
            if len(password) > MAX_PASSWORD_LENGTH:
                click.echo(f"Password too long (maximum {MAX_PASSWORD_LENGTH} characters).")
                continue
            if password.lower() in COMMON_PASSWORDS:
                click.echo("Password is too common. Choose a different one.")
                continue
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                click.echo("Passwords do not match. Try again.")
                continue
            break

        ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
        hashed = ph.hash(password)
        create_user(username, hashed, is_admin=True)
        click.echo(f"Admin account '{username}' created successfully.")


app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=app.config["DEBUG"],
    )
