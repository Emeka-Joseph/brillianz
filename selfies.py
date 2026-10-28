"""Attendance selfies: saving the live photo taken at check-in/out and purging old ones.

Photos live in SELFIE_FOLDER/<year>/<month>/ and only their relative path is kept on the Attendance row.
After SELFIE_RETENTION_DAYS the files are deleted (the attendance record and GPS location are kept).
The purge runs by itself at most every few hours while the site is in use, and can also be run by hand
with `flask --app app purge-selfies` (e.g. from Windows Task Scheduler).
"""
import base64
import binascii
import os
import secrets
import time
from datetime import date, datetime, timedelta

from flask import current_app

from models import db, Attendance

MAX_BYTES = 1_500_000  # the portal sends ~50-150 KB; anything bigger is not from our camera page
PURGE_EVERY = 6 * 3600  # seconds between automatic purges
_last_purge = 0.0


def save_selfie(data_url, employee, kind):
    """Decode the JPEG data-URL sent by the portal and store it. Returns the relative path or None."""
    if not data_url or not data_url.startswith("data:image/jpeg;base64,"):
        return None
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
    except (binascii.Error, ValueError):
        return None
    if not raw.startswith(b"\xff\xd8\xff") or len(raw) > MAX_BYTES:
        return None
    now = datetime.now()
    rel = f"{now:%Y}/{now:%m}/{employee.employee_no}_{now:%Y%m%d_%H%M%S}_{kind}_{secrets.token_hex(4)}.jpg"
    path = os.path.join(current_app.config["SELFIE_FOLDER"], *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(raw)
    return rel


def delete_files(*rels):
    folder = current_app.config["SELFIE_FOLDER"]
    for rel in rels:
        if rel:
            try:
                os.remove(os.path.join(folder, *rel.split("/")))
            except OSError:
                pass


def purge_old():
    """Delete selfies older than the retention period. Returns the number of photos removed."""
    days = current_app.config["SELFIE_RETENTION_DAYS"]
    cutoff = date.today() - timedelta(days=days)
    removed = 0
    rows = Attendance.query.filter(Attendance.work_date < cutoff,
                                   db.or_(Attendance.in_selfie.isnot(None), Attendance.out_selfie.isnot(None))).all()
    for rec in rows:
        delete_files(rec.in_selfie, rec.out_selfie)
        removed += (rec.in_selfie is not None) + (rec.out_selfie is not None)
        rec.in_selfie = rec.out_selfie = None
        rec.selfies_purged_at = datetime.utcnow()
    db.session.commit()

    # Sweep files no row points at any more (e.g. the employee or record was deleted), then empty folders.
    folder = current_app.config["SELFIE_FOLDER"]
    oldest = time.time() - days * 86400
    for root, _dirs, files in os.walk(folder, topdown=False):
        for name in files:
            path = os.path.join(root, name)
            try:
                if os.path.getmtime(path) < oldest:
                    os.remove(path)
                    removed += 1
            except OSError:
                pass
        if root != folder:
            try:
                os.rmdir(root)  # only succeeds when empty
            except OSError:
                pass
    return removed


def init_app(app):
    os.makedirs(app.config["SELFIE_FOLDER"], exist_ok=True)

    @app.before_request
    def auto_purge():
        global _last_purge
        if time.time() - _last_purge < PURGE_EVERY:
            return
        _last_purge = time.time()
        try:
            purge_old()
        except Exception:  # never block a page because the clean-up failed
            db.session.rollback()
            app.logger.exception("Selfie purge failed")

    @app.cli.command("purge-selfies")
    def purge_selfies_cmd():
        """Delete attendance selfies older than SELFIE_RETENTION_DAYS."""
        print(f"Removed {purge_old()} selfie(s).")
