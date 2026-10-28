import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "brillianz-fm-dev-secret-change-me")

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
