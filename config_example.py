"""Default configuration. Contains no secrets: every sensitive value comes from the environment or a local `.env` file.

To customise locally, either create `.env` (copy `.env.example`) or copy this file to `config.py`
(both are git-ignored). The app uses `config.py` when it exists, otherwise this file.
"""
import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def load_env(path=os.path.join(BASE_DIR, ".env")):
    """Read KEY=VALUE lines from .env into os.environ (real environment variables win)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()


class Config:
    # Without SECRET_KEY a random one is used, which signs everyone out whenever the server restarts.
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    # Set SESSION_COOKIE_SECURE=1 once the live site runs on https:// so login cookies are never sent over plain http
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # XAMPP MySQL (MariaDB) defaults: root with no password on port 3306
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", 3306))
    DB_NAME = os.environ.get("DB_NAME", "brillianz_fm")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_recycle": 280, "pool_pre_ping": True}

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB
    ALLOWED_UPLOADS = {"pdf", "doc", "docx", "jpg", "jpeg", "png"}

    # Attendance selfies: stored under uploads/selfies and deleted automatically after this many days
    SELFIE_FOLDER = os.path.join(UPLOAD_FOLDER, "selfies")
    SELFIE_RETENTION_DAYS = int(os.environ.get("SELFIE_RETENTION_DAYS", 60))

    PORT = int(os.environ.get("PORT", 7000))

    # First-run accounts (only used when the database has no admin / no demo employee yet).
    # Leave the passwords empty to have strong random ones generated and printed once in the console.
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@brillianzfm.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    DEMO_EMPLOYEE_EMAIL = os.environ.get("DEMO_EMPLOYEE_EMAIL", "employee@brillianzfm.com")
    DEMO_EMPLOYEE_PASSWORD = os.environ.get("DEMO_EMPLOYEE_PASSWORD", "")
