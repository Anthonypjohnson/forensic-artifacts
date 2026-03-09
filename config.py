import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")


class Config:
    # Core
    SECRET_KEY = os.environ.get("SECRET_KEY", "CHANGE_ME_generate_a_real_key")
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = FLASK_ENV == "development"

    # Database
    DATABASE_PATH = BASE_DIR / "database" / "artifacts.db"

    # Session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 28800  # 8 hours in seconds

    # CSRF
    WTF_CSRF_ENABLED = True

    # IP whitelist config path
    ALLOWED_IPS_CONF = BASE_DIR / "allowed_ips.conf"

    # Number of trusted reverse proxies in front of this app.
    # Set to 1 if nginx/Caddy/etc. sits in front; 0 for direct exposure.
    # ProxyFix uses this to read X-Forwarded-For correctly.
    PROXY_COUNT = int(os.environ.get("PROXY_COUNT", "0"))

    # Common passwords list
    COMMON_PASSWORDS_PATH = BASE_DIR / "static" / "common_passwords.txt"

    @classmethod
    def warn_if_default_secret(cls):
        if cls.SECRET_KEY == "CHANGE_ME_generate_a_real_key":
            if cls.FLASK_ENV != "development":
                raise RuntimeError(
                    "SECRET_KEY is set to the default placeholder value. "
                    "Generate a real key with: "
                    "python3 -c \"import secrets; print(secrets.token_hex(32))\" "
                    "and set it in your .env file before starting in production."
                )
            import warnings
            warnings.warn(
                "WARNING: SECRET_KEY is set to the default placeholder. "
                "Generate a real key before deploying to production.",
                stacklevel=2,
            )
