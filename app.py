import os
import secrets
from datetime import datetime

import pymysql
from flask import Flask, render_template, request, session, abort
from markupsafe import Markup
from flask_login import LoginManager

from config import Config
from models import db, User, Service, Office, Setting

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def ensure_database(cfg):
    """Create the MySQL database on the XAMPP server if it does not exist yet."""
    conn = pymysql.connect(host=cfg.DB_HOST, port=cfg.DB_PORT, user=cfg.DB_USER, password=cfg.DB_PASSWORD)
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{cfg.DB_NAME}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
    finally:
        conn.close()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    # Selfies arrive as a base64 form field; allow up to 2 MB per field (Werkzeug default is 500 KB)
    app.request_class.max_form_memory_size = 2 * 1024 * 1024
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    ensure_database(config_class)
    db.init_app(app)
    login_manager.init_app(app)
    import i18n
    i18n.init_app(app)
    import selfies
    selfies.init_app(app)

    from blueprints.public import bp as public_bp
    from blueprints.auth import bp as auth_bp
    from blueprints.admin import bp as admin_bp
    from blueprints.portal import bp as portal_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(portal_bp, url_prefix="/portal")

    # Lightweight CSRF protection for every POST form
    def csrf_token():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_hex(16)
        return session["_csrf"]

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
            if not sent or sent != session.get("_csrf"):
                abort(400, "Your session expired. Please go back, refresh the page and try again.")

    app.jinja_env.globals["csrf_field"] = lambda: Markup(f'<input type="hidden" name="_csrf" value="{csrf_token()}">')

    @app.context_processor
    def inject_globals():
        try:
            nav_services = Service.query.filter_by(is_active=True).order_by(Service.sort_order).all()
            offices = Office.query.order_by(Office.sort_order).all()
            site = {k: Setting.get(k) for k in ("company_name", "company_name_ar", "phone", "whatsapp", "email",
                                                  "email_ops", "years", "clients", "staff", "projects")}
        except Exception:
            nav_services, offices, site = [], [], {}
        return {"nav_services": nav_services, "offices": offices, "site": site, "now": datetime.now()}

    @app.template_filter("kwd")
    def kwd(value):
        try:
            return f"KWD {float(value):,.3f}"
        except (TypeError, ValueError):
            return "KWD 0.000"

    @app.template_filter("dt")
    def dt(value, fmt="%d %b %Y"):
        return value.strftime(fmt) if value else "—"

    @app.template_filter("label")
    def label(value):
        return (value or "").replace("_", " ").title()

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(400)
    @app.errorhandler(403)
    def other_error(e):
        return render_template("errors/error.html", code=e.code, message=e.description), e.code

    with app.app_context():
        db.create_all()
        from migrate import upgrade_schema
        upgrade_schema()
        from seed import seed_all
        seed_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=True)
