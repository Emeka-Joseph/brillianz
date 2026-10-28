"""Initial data: the licensed business activities, offices, demo staff, etc.

Runs automatically on first start (only fills empty tables), or manually:
    python seed.py
"""
import json
import random
import secrets
from datetime import date, datetime, timedelta, time

from flask import current_app

from models import (db, User, Department, Employee, Attendance, LeaveRequest, Service, WorkOrder,
                    Inquiry, JobPosting, Office, Testimonial, Setting)
from seed_content import (MAIN_PHONE, MAIN_WHATSAPP, SECURITY_SERVICE, SERVICE_ORDER, SERVICES_AR,
                          OFFICES as OFFICES_V2, PROFILE_SETTINGS, PROFILE_OFFICES, PROFILE_SERVICES,
                          RETIRED_SERVICES, RENAMED_SERVICES)

SERVICES = [
    {
        "code": "811001", "slug": "facility-management", "icon": "facility",
        "name": "Facility Management Services", "name_ar": "خدمات إدارة المرافق",
        "tagline": "One partner. Every system. Zero downtime.",
        "summary": "Integrated, end-to-end management of your property's people, places and processes, so your facility performs like clockwork every single day.",
        "description": "Our integrated facility management model brings cleaning, maintenance, security coordination, waste and vendor management under one accountable team. A dedicated facility manager, digital work orders and monthly KPI reports give you full visibility while we handle the day-to-day.",
        "features": ["Dedicated on-site facility manager", "Planned preventive maintenance (PPM) schedules",
                     "Vendor & contractor coordination", "Monthly KPI and SLA reporting",
                     "Energy & utility consumption monitoring", "24/7 helpdesk and emergency response"],
        "image": "facility-management.jpg", "image_alt": "Bright modern office floor managed by Brillianz",
    },
    {
        "code": "811006", "slug": "building-management", "icon": "building",
        "name": "Building Management Services", "name_ar": "خدمات إدارة المباني",
        "tagline": "Towers, residences and commercial complexes, run professionally.",
        "summary": "Professional administration of residential towers and commercial buildings: tenants, access, budgets, compliance and building systems.",
        "description": "From a single residential block to multi-storey towers, we act as your building's management office. We oversee tenants and visitors, coordinate security and reception, manage service charges and budgets, and keep every building system compliant with Kuwait Fire Force and municipal requirements.",
        "features": ["Tenant & visitor management", "Reception, concierge and access control",
                     "Service-charge budgeting and reporting", "Fire & life-safety compliance",
                     "Lift, generator and pump room supervision", "Owner association support"],
        "image": "building-management.jpg", "image_alt": "Glass office towers seen from street level",
    },
    {
        "code": "811002", "slug": "building-cleaning", "icon": "sparkle",
        "name": "Building Cleaning Services", "name_ar": "خدمات تنظيف المباني",
        "tagline": "Spotless lobbies, corridors and façades, every day.",
        "summary": "Daily and periodic cleaning of residential and commercial buildings, from lobbies and stairwells to windows and car parks.",
        "description": "Trained, uniformed cleaning crews keep your building immaculate on a schedule that suits your occupants. We use professional-grade equipment and certified, eco-friendly chemicals that are safe for families, staff and visitors.",
        "features": ["Lobby, corridor and stairwell cleaning", "Interior & exterior window cleaning",
                     "Car park sweeping and pressure washing", "Washroom hygiene and replenishment",
                     "Supervised day and night shifts", "Eco-friendly certified chemicals"],
        "image": "building-cleaning.jpg", "image_alt": "Cleaner in protective gloves washing a window",
    },
    {
        "code": "811003", "slug": "building-maintenance", "icon": "gear",
        "name": "Building Maintenance Services", "name_ar": "خدمات صيانة المباني",
        "tagline": "MEP experts who fix it right, the first time.",
        "summary": "Mechanical, electrical, plumbing and civil maintenance that keeps your building safe, efficient and comfortable.",
        "description": "Our multi-skilled technicians handle preventive and reactive maintenance across HVAC, electrical, plumbing, carpentry, painting and civil works. Under Kuwait's summer heat, reliable air-conditioning is critical, so our AC teams are on call around the clock.",
        "features": ["HVAC & central AC servicing", "Electrical panels, lighting and DB checks",
                     "Plumbing, drainage and water tanks", "Painting, gypsum and carpentry",
                     "Annual maintenance contracts (AMC)", "Emergency call-out response"],
        "image": "building-maintenance.jpg", "image_alt": "Technician in a hard hat working on an electrical meter",
    },
    {
        "code": "812901", "slug": "facility-cleaning", "icon": "broom",
        "name": "Cleaning Services for Buildings & Facilities", "name_ar": "خدمات تنظيف المباني والمرافق",
        "tagline": "Offices, schools, clinics and malls kept guest-ready.",
        "summary": "Tailored cleaning programmes for offices, retail, healthcare, education and hospitality facilities.",
        "description": "Every facility has its own rhythm. We design a cleaning programme around your operating hours, foot traffic and hygiene standards, then staff it with vetted cleaners and on-site supervisors who are accountable for quality audits.",
        "features": ["Office & corporate cleaning", "Retail and mall common areas",
                     "Schools and nurseries", "Clinics with infection-control protocols",
                     "Quality audits with photo reports", "Flexible staffing contracts"],
        "image": "facility-cleaning.jpg", "image_alt": "Cleaner mopping a hallway floor",
    },
    {
        "code": "812110", "slug": "cleaning-maintenance", "icon": "spray",
        "name": "Cleaning and Maintenance Services", "name_ar": "خدمات التنظيف والصيانة",
        "tagline": "Clean and maintained under one contract.",
        "summary": "Combined cleaning and light-maintenance packages so small issues are fixed before they become big costs.",
        "description": "Our combined teams clean and maintain at the same time, replacing bulbs, fixing leaking taps, re-sealing joints and reporting defects while they work. One contract, one invoice and one point of contact.",
        "features": ["Bundled cleaning + handyman visits", "Fixture and fitting repairs",
                     "Grout, silicone and sealant renewal", "Defect logging with photos",
                     "Move-in / move-out packages", "Fixed monthly pricing"],
        "image": "cleaning-maintenance.jpg", "image_alt": "Gloved hand holding a spray bottle",
    },
    {
        "code": "812902", "slug": "specialized-cleaning", "icon": "diamond",
        "name": "Specialized Cleaning Services", "name_ar": "خدمات التنظيف المتخصصة",
        "tagline": "Deep cleaning, sanitisation and restoration.",
        "summary": "Deep cleaning, post-construction cleaning, carpet and upholstery care, marble polishing, tank cleaning and disinfection.",
        "description": "When ordinary cleaning isn't enough, our specialist teams bring industrial equipment and techniques: steam extraction, marble crystallisation, high-level access cleaning, water tank sterilisation and hospital-grade disinfection fogging.",
        "features": ["Post-construction & handover cleaning", "Carpet, sofa and mattress shampooing",
                     "Marble polishing & crystallisation", "Water tank cleaning and sterilisation",
                     "Kitchen hood and duct degreasing", "Disinfection & sanitisation fogging"],
        "image": "specialized-cleaning.jpg", "image_alt": "Cordless vacuum deep cleaning a carpet",
    },
    {
        "code": "812906", "slug": "pest-control", "icon": "bug",
        "name": "Pest Control Services", "name_ar": "خدمات مكافحة الحشرات",
        "tagline": "Safe, licensed and guaranteed pest elimination.",
        "summary": "Licensed treatment and prevention against cockroaches, termites, rodents, bed bugs, mosquitoes and flies.",
        "description": "Our certified pest technicians inspect, identify and treat infestations using approved, low-odour products that are safe for children and pets. We follow up with prevention plans and scheduled visits so pests don't return.",
        "features": ["Cockroach, ant and bed-bug treatment", "Termite pre- and post-construction treatment",
                     "Rodent baiting and proofing", "Mosquito and fly control",
                     "Child- and pet-safe approved products", "Service warranty with follow-up visits"],
        "image": "pest-control.jpg", "image_alt": "Pest control technician spraying around a house",
    },
    {
        "code": "812908", "slug": "waste-collection", "icon": "recycle",
        "name": "Waste Collection and Related Services", "name_ar": "خدمات جمع النفايات والخدمات المرتبطة",
        "tagline": "Responsible collection, segregation and recycling.",
        "summary": "Scheduled waste collection, segregation, recycling and responsible disposal for buildings and facilities.",
        "description": "We manage waste from bin to final disposal: colour-coded segregation, scheduled collection, bin washing, recycling of cardboard, plastic and metal, and disposal through licensed channels, all logged so you can report on sustainability.",
        "features": ["Scheduled general waste collection", "Colour-coded segregation & recycling",
                     "Bin supply, washing and sanitising", "Bulky item and debris removal",
                     "Licensed disposal channels", "Monthly waste & recycling reports"],
        "image": "waste-collection.jpg", "image_alt": "Colour-coded recycling bins",
    },
]

DEPARTMENTS = [
    ("Management", "Executive and administrative leadership", "#0b3d5c"),
    ("Cleaning Operations", "Daily, deep and specialised cleaning crews", "#14b8a6"),
    ("Maintenance & MEP", "HVAC, electrical, plumbing and civil technicians", "#f59e0b"),
    ("Pest Control", "Licensed pest control technicians", "#84cc16"),
    ("Waste Services", "Waste collection and recycling crews", "#22c55e"),
    ("Human Resources", "Recruitment, payroll and staff welfare", "#8b5cf6"),
    ("Sales & Customer Care", "Quotations, contracts and client support", "#ec4899"),
]

OFFICES = OFFICES_V2

FIRST = ["Ahmed", "Mohammed", "Rajesh", "Joseph", "Ali", "Sameer", "Fatima", "Maria", "Anil", "Hassan",
         "Priya", "Omar", "Grace", "Yousef", "Ramesh", "Noor", "John", "Khalid", "Sunita", "Ibrahim"]
LAST = ["Al-Sabah", "Hussain", "Kumar", "Fernandes", "Mansour", "Khan", "Al-Enezi", "Santos", "Nair", "Rahman",
        "Pillai", "Haddad", "Mensah", "Al-Mutairi", "Thapa", "Abbas", "Mathew", "Al-Ajmi", "Sharma", "Farouk"]
NATIONALITIES = ["Kuwaiti", "Indian", "Egyptian", "Filipino", "Bangladeshi", "Nepali", "Pakistani", "Sri Lankan"]
TITLES = {
    "Management": ["Operations Manager", "Facility Manager"],
    "Cleaning Operations": ["Cleaning Supervisor", "Senior Cleaner", "Cleaner"],
    "Maintenance & MEP": ["HVAC Technician", "Electrician", "Plumber", "MEP Supervisor"],
    "Pest Control": ["Pest Control Technician"],
    "Waste Services": ["Waste Crew Lead", "Driver"],
    "Human Resources": ["HR Officer", "Payroll Accountant"],
    "Sales & Customer Care": ["Account Manager", "Customer Care Agent"],
}

JOBS = [
    ("HVAC Technician", "Maintenance & MEP", "Fahaheel", "Diagnose, service and repair split, package and central AC systems across client sites.",
     "3+ years HVAC experience\nValid Kuwait driving licence preferred\nKnowledge of chillers is an advantage"),
    ("Cleaning Supervisor", "Cleaning Operations", "Kuwait City", "Lead a team of 10–15 cleaners, run quality audits and liaise with clients daily.",
     "2+ years supervisory experience\nGood English; Arabic is a plus\nStrong attention to detail"),
    ("Pest Control Technician", "Pest Control", "Fahaheel", "Carry out inspections and treatments in residential and commercial properties.",
     "Pest control certification\n1+ year field experience\nSafe chemical handling knowledge"),
    ("Account Manager – FM Contracts", "Sales & Customer Care", "Kuwait City", "Grow and retain our portfolio of facility management clients.",
     "4+ years B2B sales in FM or real estate\nExcellent presentation skills\nArabic and English"),
]

def first_run_password(setting, email):
    """Password for an account created on first start: from .env, or a random one shown once in the console."""
    password = current_app.config.get(setting)
    if not password:
        password = secrets.token_urlsafe(12)
        print(f"*** Created login {email} with password: {password}  (change it after signing in) ***", flush=True)
    return password


def seed_all():
    if Setting.query.count() == 0:
        for k, v in {
            "company_name": "Brillianz Facility Management Company",
            "company_name_ar": "شركة بريليانز لإدارة المرافق",
            "phone": MAIN_PHONE,
            "whatsapp": MAIN_WHATSAPP,
            "email": "info@brillianzfm.com",
            "years": "10", "clients": "250", "staff": "400", "projects": "1800",
        }.items():
            Setting.put(k, v)

    if Service.query.count() == 0:
        for i, s in enumerate(SERVICES):
            data = dict(s)
            data["features_json"] = json.dumps(data.pop("features"))
            db.session.add(Service(sort_order=i, **data))  # Arabic + security added by upgrade_to_v2()

    if Department.query.count() == 0:
        for name, desc, color in DEPARTMENTS:
            db.session.add(Department(name=name, description=desc, color=color))

    if Office.query.count() == 0:
        for i, o in enumerate(OFFICES):
            db.session.add(Office(sort_order=i, **o))
    db.session.commit()

    if User.query.filter_by(role="admin").count() == 0:
        email = current_app.config["ADMIN_EMAIL"]
        admin = User(email=email, role="admin")
        admin.set_password(first_run_password("ADMIN_PASSWORD", email))
        db.session.add(admin)
        db.session.commit()

    if JobPosting.query.count() == 0:
        for title, dept, loc, desc, req in JOBS:
            d = Department.query.filter_by(name=dept).first()
            slug = title.lower().replace(" – ", "-").replace(" ", "-")
            db.session.add(JobPosting(title=title, slug=slug, location=loc, description=desc,
                                      requirements=req, department=d))
        db.session.commit()

    if Employee.query.count() == 0:
        seed_demo_staff()

    if int(Setting.get("data_version", "1") or 1) < 2:
        upgrade_to_v2()
        Setting.put("data_version", "2")
        db.session.commit()

    if int(Setting.get("data_version", "1") or 1) < 3:
        # Testimonials now come only from customers through testimonial links: remove the demo ones.
        Testimonial.query.delete()
        Setting.put("data_version", "3")
        db.session.commit()

    if int(Setting.get("data_version", "1") or 1) < 4:
        upgrade_to_v4()
        Setting.put("data_version", "4")
        db.session.commit()


def upgrade_to_v4():
    """Align the website with the official company profile.

    Rewrites the services to the profile's ten (renaming three in place so their history is kept,
    adding three new ones), hides the pages the profile folds into others, and updates the company
    name, phone, emails and office addresses.
    """
    for old, new in RENAMED_SERVICES.items():
        svc = Service.query.filter_by(slug=old).first()
        if svc and not Service.query.filter_by(slug=new).first():
            svc.slug = new
    db.session.flush()

    for order, data in enumerate(PROFILE_SERVICES):
        data = dict(data)
        features, features_ar = data.pop("features"), data.pop("features_ar")
        svc = Service.query.filter_by(slug=data["slug"]).first()
        if not svc:
            svc = Service(slug=data["slug"])
            db.session.add(svc)
        for k, v in data.items():
            setattr(svc, k, v)
        svc.features_json = json.dumps(features)
        svc.features_ar_json = json.dumps(features_ar, ensure_ascii=False)
        svc.sort_order, svc.is_active = order, True

    for slug in RETIRED_SERVICES:
        svc = Service.query.filter_by(slug=slug).first()
        if svc:
            svc.is_active = False
            svc.sort_order = 100

    for k, v in PROFILE_SETTINGS.items():
        Setting.put(k, v)

    for label, values in PROFILE_OFFICES.items():
        office = Office.query.filter_by(label=label).first()
        if office:
            for k, v in values.items():
                setattr(office, k, v)
    db.session.commit()


def upgrade_to_v2():
    """Security guard service, Arabic content, new head-office address and main phone/WhatsApp.

    Idempotent and careful: only fills empty Arabic fields and only replaces values that are still
    the original placeholders, so anything already edited in the admin panel is kept.
    """
    if not Service.query.filter_by(slug=SECURITY_SERVICE["slug"]).first():
        data = dict(SECURITY_SERVICE)
        data["features_json"] = json.dumps(data.pop("features"))
        db.session.add(Service(**data))
        db.session.flush()

    for order, slug in enumerate(SERVICE_ORDER):
        svc = Service.query.filter_by(slug=slug).first()
        if not svc:
            continue
        svc.sort_order = order
        ar = SERVICES_AR.get(slug, {})
        for field in ("tagline_ar", "summary_ar", "description_ar"):
            if not getattr(svc, field) and ar.get(field):
                setattr(svc, field, ar[field])
        if (not svc.features_ar_json or svc.features_ar_json == "[]") and ar.get("features_ar"):
            svc.features_ar_json = json.dumps(ar["features_ar"], ensure_ascii=False)

    if Setting.get("phone") in ("", "+965 0000 0000"):
        Setting.put("phone", MAIN_PHONE)
    if Setting.get("whatsapp") in ("", "96500000000"):
        Setting.put("whatsapp", MAIN_WHATSAPP)

    head, branch = OFFICES_V2
    old_head = Office.query.filter_by(label="Head Office").first()
    if old_head and old_head.lines.strip().replace("\r", "") in ("Kuwait City\nState of Kuwait", head["lines"]):
        for k, v in head.items():
            setattr(old_head, k, v)
        old_head.sort_order = 0
    fah = Office.query.filter_by(label="Fahaheel Branch").first()
    if fah:
        if not fah.phone:
            fah.phone = branch["phone"]
        for k in ("label_ar", "lines_ar", "hours_ar"):
            if not getattr(fah, k):
                setattr(fah, k, branch[k])
    db.session.commit()


def seed_demo_staff():
    rnd = random.Random(42)
    depts = Department.query.all()
    offices = Office.query.all()
    services = Service.query.all()
    employees = []
    for i in range(20):
        d = depts[i % len(depts)]
        e = Employee(
            employee_no=f"BFM-{1001 + i}", first_name=FIRST[i], last_name=LAST[i],
            email=f"{FIRST[i].lower()}.{LAST[i].lower().replace('-', '')}@brillianzfm.com",
            phone=f"+965 {rnd.randint(5000, 9999)} {rnd.randint(1000, 9999)}",
            nationality=rnd.choice(NATIONALITIES), job_title=rnd.choice(TITLES[d.name]),
            hire_date=date.today() - timedelta(days=rnd.randint(60, 2400)),
            residency_expiry=date.today() + timedelta(days=rnd.randint(-10, 400)),
            salary=rnd.choice([180, 220, 260, 320, 450, 600, 850, 1200]),
            status="on_leave" if i == 7 else "active", department=d, office=offices[i % len(offices)],
        )
        db.session.add(e)
        employees.append(e)
    db.session.flush()

    # A demo employee login
    email = current_app.config["DEMO_EMPLOYEE_EMAIL"]
    demo = User(email=email, role="employee")
    demo.set_password(first_run_password("DEMO_EMPLOYEE_PASSWORD", email))
    db.session.add(demo)
    employees[2].user = demo

    # Attendance for the last 10 working days (Fri/Sat weekend in Kuwait)
    for back in range(14, -1, -1):
        day = date.today() - timedelta(days=back)
        if day.weekday() in (4, 5):
            continue
        for e in employees:
            if rnd.random() < 0.08 or e.status != "active":
                continue
            late = rnd.random() < 0.15
            cin = datetime.combine(day, time(7 if not late else 8, rnd.randint(0, 59)))
            cout = None if back == 0 else cin + timedelta(hours=8, minutes=rnd.randint(0, 50))
            db.session.add(Attendance(employee=e, work_date=day, check_in=cin, check_out=cout,
                                      status="late" if late else "present"))

    for e, t, st, off, n in [(employees[7], "annual", "approved", -2, 14), (employees[3], "sick", "pending", 2, 2),
                             (employees[11], "emergency", "pending", 5, 3), (employees[15], "annual", "rejected", 20, 10)]:
        db.session.add(LeaveRequest(employee=e, leave_type=t, status=st,
                                    start_date=date.today() + timedelta(days=off),
                                    end_date=date.today() + timedelta(days=off + n - 1),
                                    reason="Family matters" if t != "sick" else "Medical rest"))

    clients = ["Al Hamra Business Tower", "Fahaheel Residences", "Salmiya Medical Clinic", "Gulf Bank Branch",
               "Mangaf Villas Compound", "Ahmadi Private School", "The Avenues Kiosk", "Sharq Office Complex"]
    statuses = ["new", "scheduled", "in_progress", "completed", "completed", "scheduled"]
    for i in range(16):
        db.session.add(WorkOrder(
            reference=f"WO-{date.today():%y%m}-{100 + i}", title=f"{services[i % 9].name.split(' Services')[0]} visit",
            client_name=clients[i % len(clients)], location=rnd.choice(["Fahaheel", "Kuwait City", "Salmiya", "Mangaf", "Ahmadi"]),
            priority=rnd.choice(WorkOrder.PRIORITIES), status=statuses[i % len(statuses)], service=services[i % 9],
            assignee=employees[(i * 3) % len(employees)], value=rnd.choice([45, 90, 150, 320, 780, 1250]),
            scheduled_date=date.today() + timedelta(days=rnd.randint(-20, 14)),
            created_at=datetime.utcnow() - timedelta(days=rnd.randint(0, 150)),
        ))

    for i, (n, svc) in enumerate([("Khalid A.", 7), ("Sara M.", 0), ("Dr. Hani", 6), ("Tower Mgmt.", 1)]):
        db.session.add(Inquiry(kind="quote" if i % 2 == 0 else "contact", name=n, phone="+965 6xxx xxxx",
                               email=f"client{i}@example.com", service=services[svc], location="Fahaheel",
                               message="Please share a quotation and earliest available date.",
                               created_at=datetime.utcnow() - timedelta(hours=i * 20)))
    db.session.commit()


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        seed_all()
        print("Seed complete.")
