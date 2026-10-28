from datetime import datetime
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, current_user

from models import db, User

bp = Blueprint("auth", __name__)


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def home_for(user):
    return url_for("admin.dashboard") if user.is_staff_manager else url_for("portal.dashboard")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if user and user.check_password(request.form.get("password", "")):
            if not user.is_active:
                flash("This account has been disabled. Please contact HR.", "error")
                return redirect(url_for("auth.login"))
            login_user(user, remember=bool(request.form.get("remember")))
            user.last_login = datetime.utcnow()
            db.session.commit()
            nxt = request.args.get("next")
            if nxt and nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(home_for(user))
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        if not current_user.check_password(request.form.get("current", "")):
            flash("Current password is incorrect.", "error")
        elif len(request.form.get("new", "")) < 8:
            flash("New password must be at least 8 characters.", "error")
        elif request.form.get("new") != request.form.get("confirm"):
            flash("Passwords do not match.", "error")
        else:
            current_user.set_password(request.form["new"])
            db.session.commit()
            flash("Password updated.", "success")
            return redirect(home_for(current_user))
    return render_template("auth/password.html")
