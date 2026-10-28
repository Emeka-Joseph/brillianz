import json
from datetime import datetime, date

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# --------------------------------------------------------------------------- #
#  Users & employees
# --------------------------------------------------------------------------- #
class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"
    ROLES = ("admin", "hr", "supervisor", "employee")

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="employee", nullable=False)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime)

    employee = db.relationship("Employee", back_populates="user", uselist=False)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_active(self):
        return self.is_active_account

    @property
    def is_staff_manager(self):
        return self.role in ("admin", "hr", "supervisor")

    @property
    def display_name(self):
        return self.employee.full_name if self.employee else self.email.split("@")[0].title()


class Department(TimestampMixin, db.Model):
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    color = db.Column(db.String(9), default="#0ea5a4")

    employees = db.relationship("Employee", back_populates="department")


class Employee(TimestampMixin, db.Model):
    __tablename__ = "employees"
    STATUSES = ("active", "on_leave", "suspended", "terminated")

    id = db.Column(db.Integer, primary_key=True)
    employee_no = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    nationality = db.Column(db.String(60))
    civil_id = db.Column(db.String(20))
    passport_no = db.Column(db.String(30))
    residency_expiry = db.Column(db.Date)
    job_title = db.Column(db.String(100))
    hire_date = db.Column(db.Date, default=date.today)
    salary = db.Column(db.Numeric(10, 3), default=0)  # KWD uses 3 decimals
    status = db.Column(db.String(20), default="active", nullable=False)
    address = db.Column(db.String(255))
    emergency_contact = db.Column(db.String(120))
    notes = db.Column(db.Text)

    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    department = db.relationship("Department", back_populates="employees")
    office_id = db.Column(db.Integer, db.ForeignKey("offices.id"))
    office = db.relationship("Office")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    user = db.relationship("User", back_populates="employee")

    attendance = db.relationship("Attendance", back_populates="employee", cascade="all, delete-orphan",
                                 order_by="desc(Attendance.work_date)")
    leaves = db.relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan",
                             order_by="desc(LeaveRequest.created_at)")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def initials(self):
        return (self.first_name[:1] + self.last_name[:1]).upper()

    @property
    def residency_days_left(self):
        if not self.residency_expiry:
            return None
        return (self.residency_expiry - date.today()).days


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (db.UniqueConstraint("employee_id", "work_date", name="uq_emp_day"),)

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    work_date = db.Column(db.Date, default=date.today, nullable=False)
    check_in = db.Column(db.DateTime)
    check_out = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="present")  # present / late / absent / remote
    note = db.Column(db.String(255))
    # Live selfie (path relative to SELFIE_FOLDER) and GPS fix captured by the portal at check-in / check-out
    in_selfie = db.Column(db.String(255))
    in_lat = db.Column(db.Float(precision=53))
    in_lng = db.Column(db.Float(precision=53))
    in_accuracy = db.Column(db.Float)  # metres
    out_selfie = db.Column(db.String(255))
    out_lat = db.Column(db.Float(precision=53))
    out_lng = db.Column(db.Float(precision=53))
    out_accuracy = db.Column(db.Float)
    selfies_purged_at = db.Column(db.DateTime)  # set when the retention job removed the photos

    employee = db.relationship("Employee", back_populates="attendance")

    @staticmethod
    def map_url(lat, lng):
        return f"https://www.google.com/maps?q={lat:.6f},{lng:.6f}" if lat is not None and lng is not None else None

    @property
    def in_map(self):
        return self.map_url(self.in_lat, self.in_lng)

    @property
    def out_map(self):
        return self.map_url(self.out_lat, self.out_lng)

    @property
    def hours(self):
        if self.check_in and self.check_out:
            return round((self.check_out - self.check_in).total_seconds() / 3600, 2)
        return None


class LeaveRequest(TimestampMixin, db.Model):
    __tablename__ = "leave_requests"
    TYPES = ("annual", "sick", "emergency", "unpaid", "hajj", "maternity")

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    leave_type = db.Column(db.String(20), default="annual")
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")  # pending / approved / rejected
    reviewed_by = db.Column(db.String(120))
    reviewed_at = db.Column(db.DateTime)

    employee = db.relationship("Employee", back_populates="leaves")

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1


# --------------------------------------------------------------------------- #
#  Services, clients & operations
# --------------------------------------------------------------------------- #
class Service(db.Model):
    __tablename__ = "services"
    id = db.Column(db.Integer, primary_key=True)
    # Licence activity code. Not unique: e.g. security guarding is delivered under 811001.
    code = db.Column(db.String(10), nullable=False, index=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    name_ar = db.Column(db.String(120))
    tagline = db.Column(db.String(200))
    tagline_ar = db.Column(db.String(200))
    summary = db.Column(db.String(400))
    summary_ar = db.Column(db.String(400))
    description = db.Column(db.Text)
    description_ar = db.Column(db.Text)
    features_json = db.Column(db.Text, default="[]")
    features_ar_json = db.Column(db.Text, default="[]")
    image = db.Column(db.String(120))
    image_alt = db.Column(db.String(120))
    icon = db.Column(db.String(40))
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    @property
    def features(self):
        try:
            return json.loads(self.features_json or "[]")
        except ValueError:
            return []

    @property
    def features_ar(self):
        try:
            return json.loads(self.features_ar_json or "[]")
        except ValueError:
            return []


class WorkOrder(TimestampMixin, db.Model):
    __tablename__ = "work_orders"
    STATUSES = ("new", "scheduled", "in_progress", "completed", "cancelled")
    PRIORITIES = ("low", "normal", "high", "urgent")

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(160), nullable=False)
    client_name = db.Column(db.String(120), nullable=False)
    client_phone = db.Column(db.String(30))
    location = db.Column(db.String(255))
    description = db.Column(db.Text)
    priority = db.Column(db.String(10), default="normal")
    status = db.Column(db.String(20), default="new")
    scheduled_date = db.Column(db.Date)
    completed_at = db.Column(db.DateTime)
    value = db.Column(db.Numeric(10, 3), default=0)

    service_id = db.Column(db.Integer, db.ForeignKey("services.id"))
    service = db.relationship("Service")
    assignee_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    assignee = db.relationship("Employee")
    inquiry_id = db.Column(db.Integer, db.ForeignKey("inquiries.id"))


class Inquiry(TimestampMixin, db.Model):
    """Contact messages and quote requests from the public website."""
    __tablename__ = "inquiries"
    STATUSES = ("new", "contacted", "quoted", "won", "lost")

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), default="contact")  # contact / quote
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    company = db.Column(db.String(120))
    property_type = db.Column(db.String(60))
    area_sqm = db.Column(db.Integer)
    location = db.Column(db.String(160))
    frequency = db.Column(db.String(40))
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default="new")

    service_id = db.Column(db.Integer, db.ForeignKey("services.id"))
    service = db.relationship("Service")


class JobPosting(TimestampMixin, db.Model):
    __tablename__ = "job_postings"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    location = db.Column(db.String(120), default="Kuwait")
    employment_type = db.Column(db.String(40), default="Full-time")
    description = db.Column(db.Text)
    requirements = db.Column(db.Text)
    is_open = db.Column(db.Boolean, default=True)

    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    department = db.relationship("Department")
    applications = db.relationship("JobApplication", back_populates="job", cascade="all, delete-orphan")


class JobApplication(TimestampMixin, db.Model):
    __tablename__ = "job_applications"
    STATUSES = ("received", "shortlisted", "interview", "hired", "rejected")

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job_postings.id"), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    nationality = db.Column(db.String(60))
    experience_years = db.Column(db.Integer)
    cover_letter = db.Column(db.Text)
    cv_filename = db.Column(db.String(255))
    status = db.Column(db.String(20), default="received")

    job = db.relationship("JobPosting", back_populates="applications")


class Office(db.Model):
    __tablename__ = "offices"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(80), nullable=False)
    label_ar = db.Column(db.String(80))
    lines = db.Column(db.Text, nullable=False)  # one address line per row
    lines_ar = db.Column(db.Text)
    phone = db.Column(db.String(40))
    email = db.Column(db.String(120))
    hours = db.Column(db.String(120))
    hours_ar = db.Column(db.String(120))
    map_query = db.Column(db.String(255))
    sort_order = db.Column(db.Integer, default=0)

    @property
    def line_list(self):
        return [l.strip() for l in (self.lines or "").splitlines() if l.strip()]

    @property
    def line_list_ar(self):
        return [l.strip() for l in (self.lines_ar or "").splitlines() if l.strip()] or self.line_list


class Testimonial(db.Model):
    """Customer review sent through a testimonial link. Shown on the website only once approved."""
    __tablename__ = "testimonials"
    STATUSES = ("pending", "approved", "rejected")

    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(120), nullable=False)
    author_ar = db.Column(db.String(120))
    role = db.Column(db.String(120))
    role_ar = db.Column(db.String(120))
    quote = db.Column(db.Text, nullable=False)
    quote_ar = db.Column(db.Text)
    rating = db.Column(db.Integer, default=5)
    status = db.Column(db.String(20), default="pending")
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_by = db.Column(db.String(120))
    reviewed_at = db.Column(db.DateTime)

    invite = db.relationship("TestimonialInvite", back_populates="testimonial", uselist=False,
                             cascade="all, delete-orphan")


class TestimonialInvite(TimestampMixin, db.Model):
    """A one-time link the admin sends to a customer to collect a testimonial."""
    __tablename__ = "testimonial_invites"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(40), unique=True, nullable=False, index=True)
    client_name = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    created_by = db.Column(db.String(120))
    used_at = db.Column(db.DateTime)

    testimonial_id = db.Column(db.Integer, db.ForeignKey("testimonials.id"))
    testimonial = db.relationship("Testimonial", back_populates="invite")


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.Text)

    @staticmethod
    def get(key, default=""):
        row = db.session.get(Setting, key)
        return row.value if row and row.value is not None else default

    @staticmethod
    def put(key, value):
        row = db.session.get(Setting, key)
        if row:
            row.value = value
        else:
            db.session.add(Setting(key=key, value=value))
