import os
import uuid
from datetime import datetime

from urllib.parse import urlparse

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from werkzeug.utils import secure_filename

from i18n import _, LANGS, COOKIE

from models import db, Service, Inquiry, JobPosting, JobApplication, Testimonial, TestimonialInvite
from seed_content import SLUG_REDIRECTS

bp = Blueprint("public", __name__)


@bp.route("/")
def home():
    services = Service.query.filter_by(is_active=True).order_by(Service.sort_order).all()
    testimonials = Testimonial.query.filter_by(status="approved").order_by(Testimonial.reviewed_at.desc()).all()
    return render_template("index.html", services=services, testimonials=testimonials)


@bp.route("/lang/<code>")
def set_language(code):
    """Switch the website language and return the visitor to the page they were on."""
    if code not in LANGS:
        abort(404)
    target = request.referrer or url_for("public.home")
    ref = urlparse(target)
    if ref.netloc and ref.netloc != request.host:  # never redirect off-site
        target = url_for("public.home")
    resp = redirect(target)
    resp.set_cookie(COOKIE, code, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


@bp.route("/services")
def services():
    services = Service.query.filter_by(is_active=True).order_by(Service.sort_order).all()
    return render_template("services.html", services=services)


@bp.route("/services/<slug>")
def service_detail(slug):
    service = Service.query.filter_by(slug=slug, is_active=True).first()
    if not service:
        if slug in SLUG_REDIRECTS:  # old service pages folded into the company-profile services
            return redirect(url_for("public.service_detail", slug=SLUG_REDIRECTS[slug]), 301)
        abort(404)
    others = Service.query.filter(Service.id != service.id, Service.is_active.is_(True)) \
        .order_by(Service.sort_order).limit(3).all()
    return render_template("service_detail.html", service=service, others=others)


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        if not request.form.get("name") or not (request.form.get("phone") or request.form.get("email")):
            flash(_("Please provide your name and a phone number or email."), "error")
            return redirect(url_for("public.contact"))
        db.session.add(Inquiry(
            kind="contact", name=request.form["name"].strip(), email=request.form.get("email"),
            phone=request.form.get("phone"), company=request.form.get("company"),
            message=request.form.get("message"), service_id=request.form.get("service_id") or None,
        ))
        db.session.commit()
        flash(_("Thank you! Our team will contact you within one business day."), "success")
        return redirect(url_for("public.contact"))
    return render_template("contact.html")


@bp.route("/quote", methods=["GET", "POST"])
def quote():
    if request.method == "POST":
        if not request.form.get("name") or not request.form.get("phone"):
            flash(_("Name and phone number are required."), "error")
            return redirect(url_for("public.quote"))
        area = request.form.get("area_sqm") or None
        db.session.add(Inquiry(
            kind="quote", name=request.form["name"].strip(), email=request.form.get("email"),
            phone=request.form.get("phone"), company=request.form.get("company"),
            property_type=request.form.get("property_type"), area_sqm=int(area) if area and area.isdigit() else None,
            location=request.form.get("location"), frequency=request.form.get("frequency"),
            message=request.form.get("message"), service_id=request.form.get("service_id") or None,
        ))
        db.session.commit()
        return render_template("quote_thanks.html", name=request.form["name"].strip())
    selected = request.args.get("service")
    return render_template("quote.html", selected=selected)


@bp.route("/testimonial/<token>", methods=["GET", "POST"])
def testimonial_form(token):
    """Personal link sent by the admin. One answer per link; it waits for approval before going public."""
    invite = TestimonialInvite.query.filter_by(token=token).first_or_404()
    if invite.used_at:
        return render_template("testimonial_thanks.html", name=invite.client_name)
    if request.method == "POST":
        name, quote = request.form.get("author", "").strip(), request.form.get("quote", "").strip()
        if not name or not quote:
            flash(_("Please enter your name and your testimonial."), "error")
            return redirect(request.url)
        rating = request.form.get("rating", type=int) or 5
        role = ", ".join(v for v in (request.form.get("position", "").strip(),
                                     request.form.get("company", "").strip()) if v)
        t = Testimonial(author=name[:120], role=role[:120] or None, quote=quote, rating=min(max(rating, 1), 5),
                        status="pending")
        invite.testimonial, invite.used_at = t, datetime.utcnow()
        db.session.add(t)
        db.session.commit()
        return render_template("testimonial_thanks.html", name=name)
    return render_template("testimonial_form.html", invite=invite)


@bp.route("/careers")
def careers():
    jobs = JobPosting.query.filter_by(is_open=True).order_by(JobPosting.created_at.desc()).all()
    return render_template("careers.html", jobs=jobs)


@bp.route("/careers/<slug>", methods=["GET", "POST"])
def career_detail(slug):
    job = JobPosting.query.filter_by(slug=slug).first_or_404()
    if not job.is_open:
        abort(404)
    if request.method == "POST":
        if not request.form.get("full_name") or not request.form.get("email"):
            flash(_("Name and email are required."), "error")
            return redirect(request.url)
        cv_name = None
        f = request.files.get("cv")
        if f and f.filename:
            ext = f.filename.rsplit(".", 1)[-1].lower()
            if ext not in current_app.config["ALLOWED_UPLOADS"]:
                flash(_("CV must be a PDF, Word document or image."), "error")
                return redirect(request.url)
            cv_name = f"{uuid.uuid4().hex[:10]}_{secure_filename(f.filename)}"
            f.save(os.path.join(current_app.config["UPLOAD_FOLDER"], cv_name))
        exp = request.form.get("experience_years")
        db.session.add(JobApplication(
            job=job, full_name=request.form["full_name"].strip(), email=request.form["email"].strip(),
            phone=request.form.get("phone"), nationality=request.form.get("nationality"),
            experience_years=int(exp) if exp and exp.isdigit() else None,
            cover_letter=request.form.get("cover_letter"), cv_filename=cv_name,
        ))
        db.session.commit()
        flash(_("Application received! Our HR team will be in touch."), "success")
        return redirect(url_for("public.careers"))
    return render_template("career_detail.html", job=job)
