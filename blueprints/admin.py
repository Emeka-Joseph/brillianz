import csv
import io
import json
import re
import secrets
from datetime import date, datetime, timedelta

from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort, Response,
                   send_from_directory, current_app)
from flask_login import current_user
from sqlalchemy import func, or_

from blueprints.auth import roles_required
from models import (db, User, Department, Employee, Attendance, LeaveRequest, Service, WorkOrder, Inquiry,
                    JobPosting, JobApplication, Office, Setting, Testimonial, TestimonialInvite)
from selfies import delete_files

bp = Blueprint("admin", __name__)

STAFF = ("admin", "hr", "supervisor")
HR = ("admin", "hr")
ADMIN = ("admin",)


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else None
    except ValueError:
        return None


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# --------------------------------------------------------------------------- #
#  Dashboard
# --------------------------------------------------------------------------- #
@bp.route("/")
@roles_required(*STAFF)
def dashboard():
    today = date.today()
    active = Employee.query.filter_by(status="active").count()
    present = Attendance.query.filter_by(work_date=today).count()
    stats = {
        "employees": Employee.query.count(),
        "active": active,
        "present": present,
        "attendance_rate": round(present / active * 100) if active else 0,
        "pending_leaves": LeaveRequest.query.filter_by(status="pending").count(),
        "open_orders": WorkOrder.query.filter(WorkOrder.status.in_(["new", "scheduled", "in_progress"])).count(),
        "new_inquiries": Inquiry.query.filter_by(status="new").count(),
        "applications": JobApplication.query.filter_by(status="received").count(),
    }

    # Work orders by status (doughnut)
    by_status = dict(db.session.query(WorkOrder.status, func.count()).group_by(WorkOrder.status).all())
    # Headcount by department (bar)
    by_dept = db.session.query(Department.name, Department.color, func.count(Employee.id)) \
        .outerjoin(Employee).group_by(Department.id).all()
    # Attendance trend last 14 days
    start = today - timedelta(days=13)
    rows = dict(db.session.query(Attendance.work_date, func.count()).filter(Attendance.work_date >= start)
                .group_by(Attendance.work_date).all())
    trend = [{"d": (start + timedelta(days=i)).strftime("%d %b"), "v": rows.get(start + timedelta(days=i), 0)}
             for i in range(14)]

    expiring = Employee.query.filter(Employee.residency_expiry.isnot(None),
                                     Employee.residency_expiry <= today + timedelta(days=60)) \
        .order_by(Employee.residency_expiry).limit(6).all()
    recent_orders = WorkOrder.query.order_by(WorkOrder.created_at.desc()).limit(6).all()
    recent_inquiries = Inquiry.query.order_by(Inquiry.created_at.desc()).limit(5).all()
    pending_leaves = LeaveRequest.query.filter_by(status="pending").order_by(LeaveRequest.start_date).limit(5).all()

    charts = {
        "status": {"labels": [s.replace("_", " ").title() for s in WorkOrder.STATUSES],
                   "values": [by_status.get(s, 0) for s in WorkOrder.STATUSES]},
        "dept": {"labels": [d[0] for d in by_dept], "colors": [d[1] for d in by_dept], "values": [d[2] for d in by_dept]},
        "trend": trend,
    }
    return render_template("admin/dashboard.html", stats=stats, charts=json.dumps(charts), expiring=expiring,
                           recent_orders=recent_orders, recent_inquiries=recent_inquiries,
                           pending_leaves=pending_leaves)


# --------------------------------------------------------------------------- #
#  Employees
# --------------------------------------------------------------------------- #
def employee_query():
    q = Employee.query
    s = request.args.get("q", "").strip()
    if s:
        like = f"%{s}%"
        q = q.filter(or_(Employee.first_name.ilike(like), Employee.last_name.ilike(like),
                         Employee.employee_no.ilike(like), Employee.job_title.ilike(like),
                         Employee.civil_id.ilike(like), Employee.phone.ilike(like)))
    if request.args.get("dept"):
        q = q.filter(Employee.department_id == request.args.get("dept", type=int))
    if request.args.get("status"):
        q = q.filter(Employee.status == request.args["status"])
    return q.order_by(Employee.employee_no)


@bp.route("/employees")
@roles_required(*STAFF)
def employees():
    return render_template("admin/employees.html", employees=employee_query().all(),
                           departments=Department.query.order_by(Department.name).all())


@bp.route("/employees/export.csv")
@roles_required(*HR)
def employees_export():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Employee No", "First name", "Last name", "Job title", "Department", "Office", "Phone", "Email",
                "Nationality", "Civil ID", "Residency expiry", "Hire date", "Salary (KWD)", "Status"])
    for e in employee_query().all():
        w.writerow([e.employee_no, e.first_name, e.last_name, e.job_title, e.department.name if e.department else "",
                    e.office.label if e.office else "", e.phone, e.email, e.nationality, e.civil_id,
                    e.residency_expiry or "", e.hire_date or "", e.salary, e.status])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=employees_{date.today()}.csv"})


def next_employee_no():
    last = Employee.query.order_by(Employee.id.desc()).first()
    n = 1001
    if last:
        m = re.search(r"(\d+)$", last.employee_no)
        n = int(m.group(1)) + 1 if m else last.id + 1001
    return f"BFM-{n}"


def fill_employee(e, form):
    for field in ("first_name", "last_name", "email", "phone", "nationality", "civil_id", "passport_no",
                  "job_title", "status", "address", "emergency_contact", "notes", "employee_no"):
        if field in form:
            setattr(e, field, form.get(field, "").strip() or None)
    e.hire_date = parse_date(form.get("hire_date"))
    e.residency_expiry = parse_date(form.get("residency_expiry"))
    e.salary = form.get("salary") or 0
    e.department_id = form.get("department_id", type=int) or None
    e.office_id = form.get("office_id", type=int) or None


@bp.route("/employees/new", methods=["GET", "POST"])
@bp.route("/employees/<int:emp_id>/edit", methods=["GET", "POST"])
@roles_required(*HR)
def employee_form(emp_id=None):
    e = db.session.get(Employee, emp_id) if emp_id else Employee(employee_no=next_employee_no(), status="active")
    if emp_id and not e:
        abort(404)
    if request.method == "POST":
        if not request.form.get("first_name") or not request.form.get("last_name"):
            flash("First and last name are required.", "error")
        else:
            fill_employee(e, request.form)
            dup = Employee.query.filter(Employee.employee_no == e.employee_no, Employee.id != (e.id or 0)).first()
            if dup:
                flash(f"Employee number {e.employee_no} is already used.", "error")
            else:
                db.session.add(e)
                db.session.commit()
                flash(f"{e.full_name} saved.", "success")
                return redirect(url_for("admin.employee_view", emp_id=e.id))
    return render_template("admin/employee_form.html", e=e,
                           departments=Department.query.order_by(Department.name).all(),
                           offices=Office.query.order_by(Office.sort_order).all())


@bp.route("/employees/<int:emp_id>")
@roles_required(*STAFF)
def employee_view(emp_id):
    e = db.session.get(Employee, emp_id) or abort(404)
    orders = WorkOrder.query.filter_by(assignee_id=e.id).order_by(WorkOrder.created_at.desc()).limit(10).all()
    month_start = date.today().replace(day=1)
    month_att = [a for a in e.attendance if a.work_date >= month_start]
    hours = sum(a.hours or 0 for a in month_att)
    return render_template("admin/employee_view.html", e=e, orders=orders, month_days=len(month_att),
                           month_hours=round(hours, 1))


@bp.route("/employees/<int:emp_id>/delete", methods=["POST"])
@roles_required(*HR)
def employee_delete(emp_id):
    e = db.session.get(Employee, emp_id) or abort(404)
    WorkOrder.query.filter_by(assignee_id=e.id).update({"assignee_id": None})
    for a in e.attendance:
        delete_files(a.in_selfie, a.out_selfie)
    if e.user:
        db.session.delete(e.user)
    db.session.delete(e)
    db.session.commit()
    flash("Employee removed.", "success")
    return redirect(url_for("admin.employees"))


@bp.route("/employees/<int:emp_id>/account", methods=["POST"])
@roles_required(*HR)
def employee_account(emp_id):
    e = db.session.get(Employee, emp_id) or abort(404)
    email = (request.form.get("login_email") or e.email or "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "employee")
    if role not in User.ROLES or (role == "admin" and current_user.role != "admin"):
        abort(403)
    if not email or len(password) < 8:
        flash("A login email and a password of at least 8 characters are required.", "error")
        return redirect(url_for("admin.employee_view", emp_id=e.id))
    user = e.user or User.query.filter_by(email=email).first()
    if user and user.employee and user.employee.id != e.id:
        flash("That email is already linked to another employee.", "error")
        return redirect(url_for("admin.employee_view", emp_id=e.id))
    if not user:
        user = User(email=email)
        db.session.add(user)
    user.email, user.role, user.is_active_account = email, role, True
    user.set_password(password)
    e.user = user
    db.session.commit()
    flash(f"Portal login ready for {e.full_name} ({email}).", "success")
    return redirect(url_for("admin.employee_view", emp_id=e.id))


# --------------------------------------------------------------------------- #
#  Departments
# --------------------------------------------------------------------------- #
@bp.route("/departments", methods=["GET", "POST"])
@roles_required(*HR)
def departments():
    if request.method == "POST":
        dep_id = request.form.get("id", type=int)
        d = db.session.get(Department, dep_id) if dep_id else Department()
        d.name = request.form.get("name", "").strip()
        d.description = request.form.get("description")
        d.color = request.form.get("color") or "#0ea5a4"
        if not d.name:
            flash("Name is required.", "error")
        else:
            db.session.add(d)
            db.session.commit()
            flash("Department saved.", "success")
        return redirect(url_for("admin.departments"))
    rows = db.session.query(Department, func.count(Employee.id)).outerjoin(Employee) \
        .group_by(Department.id).order_by(Department.name).all()
    return render_template("admin/departments.html", rows=rows)


@bp.route("/departments/<int:dep_id>/delete", methods=["POST"])
@roles_required(*HR)
def department_delete(dep_id):
    d = db.session.get(Department, dep_id) or abort(404)
    if d.employees:
        flash("Move employees out of this department before deleting it.", "error")
    else:
        db.session.delete(d)
        db.session.commit()
        flash("Department deleted.", "success")
    return redirect(url_for("admin.departments"))


# --------------------------------------------------------------------------- #
#  Attendance
# --------------------------------------------------------------------------- #
@bp.route("/attendance", methods=["GET", "POST"])
@roles_required(*STAFF)
def attendance():
    day = parse_date(request.values.get("day")) or date.today()
    if request.method == "POST":
        for e in Employee.query.filter(Employee.status.in_(["active", "on_leave"])).all():
            status = request.form.get(f"status_{e.id}")
            rec = Attendance.query.filter_by(employee_id=e.id, work_date=day).first()
            if not status:
                if rec:
                    delete_files(rec.in_selfie, rec.out_selfie)
                    db.session.delete(rec)
                continue
            if not rec:
                rec = Attendance(employee_id=e.id, work_date=day)
                db.session.add(rec)
            rec.status = status
            for field in ("check_in", "check_out"):
                t = request.form.get(f"{field}_{e.id}")
                setattr(rec, field, datetime.combine(day, datetime.strptime(t, "%H:%M").time()) if t else None)
        db.session.commit()
        flash(f"Attendance for {day:%d %b %Y} saved.", "success")
        return redirect(url_for("admin.attendance", day=day.isoformat()))
    emps = Employee.query.filter(Employee.status.in_(["active", "on_leave"])).order_by(Employee.employee_no).all()
    records = {a.employee_id: a for a in Attendance.query.filter_by(work_date=day).all()}
    return render_template("admin/attendance.html", day=day, employees=emps, records=records,
                           prev=day - timedelta(days=1), next=day + timedelta(days=1),
                           retention=current_app.config["SELFIE_RETENTION_DAYS"])


@bp.route("/attendance/selfie/<path:filename>")
@roles_required(*STAFF)
def attendance_selfie(filename):
    return send_from_directory(current_app.config["SELFIE_FOLDER"], filename, max_age=3600)


@bp.route("/attendance/report")
@roles_required(*STAFF)
def attendance_report():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    try:
        start = datetime.strptime(month + "-01", "%Y-%m-%d").date()
    except ValueError:
        start = date.today().replace(day=1)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    rows = db.session.query(Employee, func.count(Attendance.id),
                            func.sum(db.case((Attendance.status == "late", 1), else_=0))) \
        .outerjoin(Attendance, db.and_(Attendance.employee_id == Employee.id, Attendance.work_date >= start,
                                       Attendance.work_date < end)) \
        .group_by(Employee.id).order_by(Employee.employee_no).all()
    working_days = sum(1 for i in range((min(end, date.today() + timedelta(days=1)) - start).days)
                       if (start + timedelta(days=i)).weekday() not in (4, 5))
    return render_template("admin/attendance_report.html", rows=rows, month=start, working_days=working_days)


# --------------------------------------------------------------------------- #
#  Leave
# --------------------------------------------------------------------------- #
@bp.route("/leaves")
@roles_required(*STAFF)
def leaves():
    status = request.args.get("status", "pending")
    q = LeaveRequest.query
    if status != "all":
        q = q.filter_by(status=status)
    return render_template("admin/leaves.html", leaves=q.order_by(LeaveRequest.start_date.desc()).all(),
                           status=status, employees=Employee.query.order_by(Employee.first_name).all(),
                           types=LeaveRequest.TYPES)


@bp.route("/leaves/new", methods=["POST"])
@roles_required(*HR)
def leave_new():
    s, e = parse_date(request.form.get("start_date")), parse_date(request.form.get("end_date"))
    if not s or not e or e < s:
        flash("Please enter a valid date range.", "error")
    else:
        db.session.add(LeaveRequest(employee_id=request.form.get("employee_id", type=int), start_date=s, end_date=e,
                                    leave_type=request.form.get("leave_type"), reason=request.form.get("reason"),
                                    status="approved", reviewed_by=current_user.display_name,
                                    reviewed_at=datetime.utcnow()))
        db.session.commit()
        flash("Leave recorded.", "success")
    return redirect(url_for("admin.leaves", status="all"))


@bp.route("/leaves/<int:leave_id>/<action>", methods=["POST"])
@roles_required(*HR)
def leave_review(leave_id, action):
    lv = db.session.get(LeaveRequest, leave_id) or abort(404)
    if action not in ("approve", "reject"):
        abort(400)
    lv.status = "approved" if action == "approve" else "rejected"
    lv.reviewed_by = current_user.display_name
    lv.reviewed_at = datetime.utcnow()
    if lv.status == "approved" and lv.start_date <= date.today() <= lv.end_date:
        lv.employee.status = "on_leave"
    db.session.commit()
    flash(f"Leave {lv.status} for {lv.employee.full_name}.", "success")
    return redirect(request.referrer or url_for("admin.leaves"))


# --------------------------------------------------------------------------- #
#  Work orders
# --------------------------------------------------------------------------- #
@bp.route("/work-orders")
@roles_required(*STAFF)
def work_orders():
    q = WorkOrder.query
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    if request.args.get("service"):
        q = q.filter_by(service_id=request.args.get("service", type=int))
    return render_template("admin/work_orders.html", orders=q.order_by(WorkOrder.created_at.desc()).all(),
                           services=Service.query.order_by(Service.sort_order).all(), statuses=WorkOrder.STATUSES)


@bp.route("/work-orders/new", methods=["GET", "POST"])
@bp.route("/work-orders/<int:wo_id>/edit", methods=["GET", "POST"])
@roles_required(*STAFF)
def work_order_form(wo_id=None):
    if wo_id:
        wo = db.session.get(WorkOrder, wo_id) or abort(404)
    else:
        count = WorkOrder.query.count()
        wo = WorkOrder(reference=f"WO-{date.today():%y%m}-{100 + count + 1}", status="new", priority="normal")
        inquiry = db.session.get(Inquiry, request.args.get("inquiry", type=int) or 0)
        if inquiry:
            wo.client_name, wo.client_phone, wo.location = inquiry.company or inquiry.name, inquiry.phone, inquiry.location
            wo.service_id, wo.description, wo.inquiry_id = inquiry.service_id, inquiry.message, inquiry.id
            wo.title = f"{inquiry.service.name if inquiry.service else 'Service'} for {inquiry.name}"
    if request.method == "POST":
        f = request.form
        wo.title, wo.client_name = f.get("title", "").strip(), f.get("client_name", "").strip()
        if not wo.title or not wo.client_name:
            flash("Title and client are required.", "error")
        else:
            wo.client_phone, wo.location, wo.description = f.get("client_phone"), f.get("location"), f.get("description")
            wo.priority, wo.value = f.get("priority", "normal"), f.get("value") or 0
            new_status = f.get("status", "new")
            if new_status == "completed" and wo.status != "completed":
                wo.completed_at = datetime.utcnow()
            wo.status = new_status
            wo.scheduled_date = parse_date(f.get("scheduled_date"))
            wo.service_id = f.get("service_id", type=int) or None
            wo.assignee_id = f.get("assignee_id", type=int) or None
            wo.inquiry_id = f.get("inquiry_id", type=int) or wo.inquiry_id
            db.session.add(wo)
            if wo.inquiry_id:
                inq = db.session.get(Inquiry, wo.inquiry_id)
                if inq and inq.status in ("new", "contacted"):
                    inq.status = "won"
            db.session.commit()
            flash(f"Work order {wo.reference} saved.", "success")
            return redirect(url_for("admin.work_orders"))
    return render_template("admin/work_order_form.html", wo=wo,
                           services=Service.query.order_by(Service.sort_order).all(),
                           employees=Employee.query.filter_by(status="active").order_by(Employee.first_name).all())


@bp.route("/work-orders/<int:wo_id>/delete", methods=["POST"])
@roles_required(*ADMIN)
def work_order_delete(wo_id):
    db.session.delete(db.session.get(WorkOrder, wo_id) or abort(404))
    db.session.commit()
    flash("Work order deleted.", "success")
    return redirect(url_for("admin.work_orders"))


# --------------------------------------------------------------------------- #
#  Inquiries / quotes
# --------------------------------------------------------------------------- #
@bp.route("/inquiries")
@roles_required(*STAFF)
def inquiries():
    q = Inquiry.query
    if request.args.get("kind"):
        q = q.filter_by(kind=request.args["kind"])
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    return render_template("admin/inquiries.html", inquiries=q.order_by(Inquiry.created_at.desc()).all(),
                           statuses=Inquiry.STATUSES)


@bp.route("/inquiries/<int:inq_id>/status", methods=["POST"])
@roles_required(*STAFF)
def inquiry_status(inq_id):
    inq = db.session.get(Inquiry, inq_id) or abort(404)
    if request.form.get("status") in Inquiry.STATUSES:
        inq.status = request.form["status"]
        db.session.commit()
        flash("Inquiry updated.", "success")
    return redirect(request.referrer or url_for("admin.inquiries"))


@bp.route("/inquiries/<int:inq_id>/delete", methods=["POST"])
@roles_required(*ADMIN)
def inquiry_delete(inq_id):
    db.session.delete(db.session.get(Inquiry, inq_id) or abort(404))
    db.session.commit()
    flash("Inquiry deleted.", "success")
    return redirect(url_for("admin.inquiries"))


# --------------------------------------------------------------------------- #
#  Recruitment
# --------------------------------------------------------------------------- #
@bp.route("/jobs", methods=["GET", "POST"])
@roles_required(*HR)
def jobs():
    if request.method == "POST":
        job_id = request.form.get("id", type=int)
        j = db.session.get(JobPosting, job_id) if job_id else JobPosting()
        j.title = request.form.get("title", "").strip()
        if not j.title:
            flash("Title is required.", "error")
            return redirect(url_for("admin.jobs"))
        if not j.slug:
            base, n = slugify(j.title), 1
            j.slug = base
            while JobPosting.query.filter_by(slug=j.slug).first():
                n += 1
                j.slug = f"{base}-{n}"
        j.location = request.form.get("location") or "Kuwait"
        j.employment_type = request.form.get("employment_type") or "Full-time"
        j.description, j.requirements = request.form.get("description"), request.form.get("requirements")
        j.department_id = request.form.get("department_id", type=int) or None
        j.is_open = bool(request.form.get("is_open"))
        db.session.add(j)
        db.session.commit()
        flash("Job posting saved.", "success")
        return redirect(url_for("admin.jobs"))
    return render_template("admin/jobs.html", jobs=JobPosting.query.order_by(JobPosting.created_at.desc()).all(),
                           departments=Department.query.order_by(Department.name).all())


@bp.route("/jobs/<int:job_id>/delete", methods=["POST"])
@roles_required(*HR)
def job_delete(job_id):
    db.session.delete(db.session.get(JobPosting, job_id) or abort(404))
    db.session.commit()
    flash("Job posting deleted.", "success")
    return redirect(url_for("admin.jobs"))


@bp.route("/applications")
@roles_required(*HR)
def applications():
    q = JobApplication.query
    if request.args.get("job"):
        q = q.filter_by(job_id=request.args.get("job", type=int))
    return render_template("admin/applications.html",
                           applications=q.order_by(JobApplication.created_at.desc()).all(),
                           statuses=JobApplication.STATUSES)


@bp.route("/applications/<int:app_id>/status", methods=["POST"])
@roles_required(*HR)
def application_status(app_id):
    a = db.session.get(JobApplication, app_id) or abort(404)
    if request.form.get("status") in JobApplication.STATUSES:
        a.status = request.form["status"]
        db.session.commit()
        flash("Application updated.", "success")
    return redirect(request.referrer or url_for("admin.applications"))


@bp.route("/applications/<int:app_id>/hire", methods=["POST"])
@roles_required(*HR)
def application_hire(app_id):
    a = db.session.get(JobApplication, app_id) or abort(404)
    parts = a.full_name.split(" ", 1)
    e = Employee(employee_no=next_employee_no(), first_name=parts[0], last_name=parts[1] if len(parts) > 1 else "-",
                 email=a.email, phone=a.phone, nationality=a.nationality, job_title=a.job.title,
                 department_id=a.job.department_id, status="active", hire_date=date.today())
    a.status = "hired"
    db.session.add(e)
    db.session.commit()
    flash(f"{e.full_name} added to employees. Complete their profile.", "success")
    return redirect(url_for("admin.employee_form", emp_id=e.id))


@bp.route("/applications/cv/<path:filename>")
@roles_required(*HR)
def application_cv(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


# --------------------------------------------------------------------------- #
#  Website content & settings (admin only)
# --------------------------------------------------------------------------- #
@bp.route("/offices", methods=["GET", "POST"])
@roles_required(*ADMIN)
def offices():
    if request.method == "POST":
        off_id = request.form.get("id", type=int)
        o = db.session.get(Office, off_id) if off_id else Office(sort_order=Office.query.count())
        o.label, o.lines = request.form.get("label", "").strip(), request.form.get("lines", "").strip()
        if not o.label or not o.lines:
            flash("Label and address are required.", "error")
            return redirect(url_for("admin.offices"))
        o.phone, o.email = request.form.get("phone"), request.form.get("email")
        o.hours, o.map_query = request.form.get("hours"), request.form.get("map_query")
        o.label_ar, o.lines_ar = request.form.get("label_ar"), request.form.get("lines_ar")
        o.hours_ar = request.form.get("hours_ar")
        db.session.add(o)
        db.session.commit()
        flash("Office saved.", "success")
        return redirect(url_for("admin.offices"))
    return render_template("admin/offices.html", items=Office.query.order_by(Office.sort_order).all())


@bp.route("/offices/<int:off_id>/delete", methods=["POST"])
@roles_required(*ADMIN)
def office_delete(off_id):
    o = db.session.get(Office, off_id) or abort(404)
    Employee.query.filter_by(office_id=o.id).update({"office_id": None})
    db.session.delete(o)
    db.session.commit()
    flash("Office removed.", "success")
    return redirect(url_for("admin.offices"))


@bp.route("/services", methods=["GET"])
@roles_required(*ADMIN)
def services():
    return render_template("admin/services.html", services=Service.query.order_by(Service.sort_order).all())


@bp.route("/services/<int:svc_id>", methods=["GET", "POST"])
@roles_required(*ADMIN)
def service_edit(svc_id):
    s = db.session.get(Service, svc_id) or abort(404)
    if request.method == "POST":
        for field in ("name", "name_ar", "tagline", "tagline_ar", "summary", "summary_ar", "description", "description_ar"):
            setattr(s, field, request.form.get(field, "").strip())
        s.features_json = json.dumps([l.strip() for l in request.form.get("features", "").splitlines() if l.strip()])
        s.features_ar_json = json.dumps([l.strip() for l in request.form.get("features_ar", "").splitlines() if l.strip()],
                                        ensure_ascii=False)
        s.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Service updated.", "success")
        return redirect(url_for("admin.services"))
    return render_template("admin/service_edit.html", s=s)


@bp.route("/settings", methods=["GET", "POST"])
@roles_required(*ADMIN)
def settings():
    keys = ["company_name", "company_name_ar", "phone", "whatsapp", "email", "years", "clients", "staff", "projects"]
    if request.method == "POST":
        for k in keys:
            Setting.put(k, request.form.get(k, "").strip())
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", values={k: Setting.get(k) for k in keys})


# --------------------------------------------------------------------------- #
#  Testimonials: links sent to customers, then reviewed before going public
# --------------------------------------------------------------------------- #
@bp.context_processor
def pending_testimonials():
    if current_user.is_authenticated and current_user.role in ADMIN:
        return {"pending_testimonials": Testimonial.query.filter_by(status="pending").count()}
    return {}


@bp.route("/testimonials")
@roles_required(*ADMIN)
def testimonials():
    status = request.args.get("status", "pending")
    if status not in Testimonial.STATUSES:
        status = "pending"
    items = Testimonial.query.filter_by(status=status).order_by(Testimonial.submitted_at.desc()).all()
    counts = dict(db.session.query(Testimonial.status, func.count()).group_by(Testimonial.status).all())
    invites = TestimonialInvite.query.filter_by(used_at=None).order_by(TestimonialInvite.created_at.desc()).all()
    new_invite = db.session.get(TestimonialInvite, request.args.get("new", type=int) or 0)
    return render_template("admin/testimonials.html", items=items, status=status, counts=counts,
                           invites=invites, new_invite=new_invite)


@bp.route("/testimonials/invite", methods=["POST"])
@roles_required(*ADMIN)
def testimonial_invite():
    name = request.form.get("client_name", "").strip()
    if not name:
        flash("Enter the customer's name to create a link.", "error")
        return redirect(url_for("admin.testimonials"))
    inv = TestimonialInvite(token=secrets.token_urlsafe(16), client_name=name,
                            company=request.form.get("company", "").strip() or None,
                            email=request.form.get("email", "").strip() or None,
                            phone=request.form.get("phone", "").strip() or None,
                            created_by=current_user.display_name)
    db.session.add(inv)
    db.session.commit()
    flash(f"Testimonial link created for {name}. Copy it or send it below.", "success")
    return redirect(url_for("admin.testimonials", new=inv.id))


@bp.route("/testimonials/invite/<int:inv_id>/delete", methods=["POST"])
@roles_required(*ADMIN)
def testimonial_invite_delete(inv_id):
    inv = db.session.get(TestimonialInvite, inv_id) or abort(404)
    db.session.delete(inv)
    db.session.commit()
    flash("Link cancelled. The customer can no longer use it.", "success")
    return redirect(url_for("admin.testimonials"))


@bp.route("/testimonials/<int:t_id>", methods=["POST"])
@roles_required(*ADMIN)
def testimonial_review(t_id):
    t = db.session.get(Testimonial, t_id) or abort(404)
    action = request.form.get("action")
    if action == "delete":
        db.session.delete(t)
        db.session.commit()
        flash("Testimonial deleted.", "success")
        return redirect(url_for("admin.testimonials", status=t.status))

    for field in ("author", "role", "quote", "author_ar", "role_ar", "quote_ar"):
        setattr(t, field, request.form.get(field, "").strip() or None)
    if not t.author or not t.quote:
        flash("Name and testimonial text cannot be empty.", "error")
        return redirect(url_for("admin.testimonials", status=t.status))
    if action in ("approve", "reject"):
        t.status = "approved" if action == "approve" else "rejected"
        t.reviewed_by, t.reviewed_at = current_user.display_name, datetime.utcnow()
    db.session.commit()
    flash({"approve": "Testimonial approved. It is now on the website.",
           "reject": "Testimonial rejected. It will not be shown on the website."}.get(action, "Testimonial saved."),
          "success")
    return redirect(url_for("admin.testimonials", status=t.status))


@bp.route("/users", methods=["GET", "POST"])
@roles_required(*ADMIN)
def users():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email or len(request.form.get("password", "")) < 8:
            flash("Email and a password of 8+ characters are required.", "error")
        elif User.query.filter_by(email=email).first():
            flash("A user with that email already exists.", "error")
        else:
            u = User(email=email, role=request.form.get("role", "hr"))
            u.set_password(request.form["password"])
            db.session.add(u)
            db.session.commit()
            flash("User created.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/users.html", users=User.query.order_by(User.role, User.email).all(), roles=User.ROLES)


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@roles_required(*ADMIN)
def user_toggle(user_id):
    u = db.session.get(User, user_id) or abort(404)
    if u.id == current_user.id:
        flash("You cannot disable your own account.", "error")
    else:
        u.is_active_account = not u.is_active_account
        db.session.commit()
        flash(f"{u.email} {'enabled' if u.is_active_account else 'disabled'}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@roles_required(*ADMIN)
def user_role(user_id):
    u = db.session.get(User, user_id) or abort(404)
    if request.form.get("role") in User.ROLES and u.id != current_user.id:
        u.role = request.form["role"]
        db.session.commit()
        flash("Role updated.", "success")
    return redirect(url_for("admin.users"))
