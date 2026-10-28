"""Employee self-service portal: clock in/out, leave requests, assigned jobs."""
from datetime import date, datetime, time

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from models import db, Attendance, LeaveRequest, WorkOrder
from selfies import save_selfie

bp = Blueprint("portal", __name__)

SHIFT_START = time(8, 15)  # check-ins after this are marked late


def me():
    if not current_user.employee:
        abort(403)
    return current_user.employee


@bp.route("/")
@login_required
def dashboard():
    if not current_user.employee:
        if current_user.is_staff_manager:
            return redirect(url_for("admin.dashboard"))
        abort(403)
    e = me()
    today = Attendance.query.filter_by(employee_id=e.id, work_date=date.today()).first()
    orders = WorkOrder.query.filter(WorkOrder.assignee_id == e.id,
                                    WorkOrder.status.in_(["new", "scheduled", "in_progress"])) \
        .order_by(WorkOrder.scheduled_date).all()
    year_start = date(date.today().year, 1, 1)
    used = sum(l.days for l in e.leaves if l.status == "approved" and l.leave_type == "annual"
               and l.start_date >= year_start)
    return render_template("portal/dashboard.html", e=e, today=today, orders=orders,
                           recent=e.attendance[:10], leave_used=used, leave_balance=max(30 - used, 0))


def read_location(form):
    try:
        lat, lng = float(form["lat"]), float(form["lng"])
        acc = float(form.get("accuracy") or 0) or None
    except (KeyError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng, acc


@bp.route("/clock", methods=["POST"])
@login_required
def clock():
    """Check in / check out. Both require a live selfie and the phone's GPS location."""
    e = me()
    now = datetime.now()
    rec = Attendance.query.filter_by(employee_id=e.id, work_date=now.date()).first()
    if rec and rec.check_out:
        flash("You have already completed today's attendance.", "info")
        return redirect(url_for("portal.dashboard"))
    loc = read_location(request.form)
    if not loc:
        flash("We couldn't read your location. Allow location access and try again.", "error")
        return redirect(url_for("portal.dashboard"))
    kind = "out" if rec else "in"
    photo = save_selfie(request.form.get("selfie"), e, kind)
    if not photo:
        flash("A live selfie is required. Allow camera access and take your photo.", "error")
        return redirect(url_for("portal.dashboard"))
    lat, lng, acc = loc
    if not rec:
        db.session.add(Attendance(employee_id=e.id, work_date=now.date(), check_in=now,
                                  status="late" if now.time() > SHIFT_START else "present",
                                  in_selfie=photo, in_lat=lat, in_lng=lng, in_accuracy=acc))
        flash(f"Checked in at {now:%H:%M}. Have a brilliant day!", "success")
    else:
        rec.check_out = now
        rec.out_selfie, rec.out_lat, rec.out_lng, rec.out_accuracy = photo, lat, lng, acc
        flash(f"Checked out at {now:%H:%M}. Thank you!", "success")
    db.session.commit()
    return redirect(url_for("portal.dashboard"))


@bp.route("/leave", methods=["GET", "POST"])
@login_required
def leave():
    e = me()
    if request.method == "POST":
        try:
            s = datetime.strptime(request.form["start_date"], "%Y-%m-%d").date()
            en = datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            s = en = None
        if not s or not en or en < s:
            flash("Please choose a valid date range.", "error")
        elif request.form.get("leave_type") not in LeaveRequest.TYPES:
            flash("Please choose a leave type.", "error")
        else:
            db.session.add(LeaveRequest(employee_id=e.id, leave_type=request.form["leave_type"], start_date=s,
                                        end_date=en, reason=request.form.get("reason")))
            db.session.commit()
            flash("Leave request submitted for approval.", "success")
            return redirect(url_for("portal.leave"))
    return render_template("portal/leave.html", e=e, types=LeaveRequest.TYPES)


@bp.route("/jobs/<int:wo_id>/status", methods=["POST"])
@login_required
def job_status(wo_id):
    e = me()
    wo = db.session.get(WorkOrder, wo_id) or abort(404)
    if wo.assignee_id != e.id:
        abort(403)
    st = request.form.get("status")
    if st in ("in_progress", "completed"):
        wo.status = st
        if st == "completed":
            wo.completed_at = datetime.utcnow()
        db.session.commit()
        flash(f"{wo.reference} marked {st.replace('_', ' ')}.", "success")
    return redirect(url_for("portal.dashboard"))


@bp.route("/profile")
@login_required
def profile():
    return render_template("portal/profile.html", e=me())
