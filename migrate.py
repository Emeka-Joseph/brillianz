"""Tiny additive schema upgrader: brings an existing MySQL database up to date with models.py.

db.create_all() only creates missing tables, so new columns on existing tables are added here.
Only ever ADDs columns/indexes (and relaxes services.code from unique); never drops data.
"""
from sqlalchemy import inspect, text

from models import db

NEW_COLUMNS = {
    "services": {
        "tagline_ar": "VARCHAR(200)", "summary_ar": "VARCHAR(400)",
        "description_ar": "TEXT", "features_ar_json": "TEXT",
    },
    "offices": {"label_ar": "VARCHAR(80)", "lines_ar": "TEXT", "hours_ar": "VARCHAR(120)"},
    "testimonials": {"author_ar": "VARCHAR(120)", "role_ar": "VARCHAR(120)", "quote_ar": "TEXT",
                     "status": "VARCHAR(20)", "submitted_at": "DATETIME", "reviewed_by": "VARCHAR(120)",
                     "reviewed_at": "DATETIME"},
    "attendance": {"in_selfie": "VARCHAR(255)", "in_lat": "DOUBLE", "in_lng": "DOUBLE", "in_accuracy": "FLOAT",
                   "out_selfie": "VARCHAR(255)", "out_lat": "DOUBLE", "out_lng": "DOUBLE", "out_accuracy": "FLOAT",
                   "selfies_purged_at": "DATETIME"},
}


def upgrade_schema():
    insp = inspect(db.engine)
    with db.engine.begin() as conn:
        for table, cols in NEW_COLUMNS.items():
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{name}` {ddl} NULL"))

        # services.code used to be UNIQUE; several services can share one licence activity code.
        indexes = insp.get_indexes("services")
        for ix in indexes:
            if ix["column_names"] == ["code"] and ix.get("unique"):
                conn.execute(text(f"ALTER TABLE `services` DROP INDEX `{ix['name']}`"))
        if not any(ix["column_names"] == ["code"] and not ix.get("unique") for ix in indexes):
            conn.execute(text("CREATE INDEX `ix_services_code` ON `services` (`code`)"))
