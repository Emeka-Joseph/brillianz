# Brillianz Facility Management Company: website & staff portal

Flask + MySQL (XAMPP) website with an employee-management back office.

## Run
1. Start **MySQL** in the XAMPP control panel.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your own values (secret key, database login, first admin account).
   `.env` and `config.py` are git-ignored, so passwords and keys never reach the repository.
4. `python app.py` and open **http://127.0.0.1:7000**

The `brillianz_fm` database, tables and demo data are created automatically on first start, and
existing databases are upgraded in place on start-up (`migrate.py` adds new columns; `seed.py` applies one-time data updates).
Upgrading from the old `brilliant_fm` database? Stop the site and run `python rename_db.py` once.

## First login
On the very first start the admin and demo employee accounts are created with the passwords from `.env`
(`ADMIN_PASSWORD`, `DEMO_EMPLOYEE_PASSWORD`). If those are empty, random passwords are generated and printed once
in the console. Change them after signing in (sidebar → Change password).

## What's inside
- **English / Arabic**: every public page has a full Arabic version (right-to-left layout, Arabic font). The language
  switch (globe button) sits in the sticky header on every page and phone, plus the top bar, mobile menu and footer.
  Interface text lives in `translations_ar.py`; Arabic service, office and testimonial text is editable in the admin.
- **Public site**: content follows the official company profile PDF: the 10 profile
  services, the complete-property-management approach (animated "one accountable manager" diagram), hard & soft
  services, the monthly owner report (animated illustration), vision & mission, quality & HSE policies and the team
  chart. Home has a photo slideshow, soap-bubble animation, counters and a before/after slider; every service page has
  an animated scene. Old service links (security, building management, facility cleaning, etc.) redirect to the new pages.
- **Back office** (`/admin`): dashboard with charts, employees (Civil ID, residency expiry alerts, KWD salary, CSV export),
  departments, daily attendance + monthly report, leave approval, work orders, website leads → work orders,
  job postings & applications (one-click hire), editable services / offices / settings / testimonials, users & roles.
- **Employee portal** (`/portal`): live clock-in/out with a required live selfie + GPS location, assigned jobs, leave requests and balance, profile.

## Selfie check-in
Every check in / check out on the employee portal requires a live camera selfie and the phone's GPS location.
Admins, HR and supervisors see the photos (click to enlarge) and a Google Maps link on **Attendance** and on each
employee's profile. Photos are saved in `uploads/selfies/` and deleted automatically after 60 days (set
`SELFIE_RETENTION_DAYS` to change); the attendance times and locations are kept. The clean-up runs by itself every few
hours while the site is in use, or by hand: `flask --app app purge-selfies`.

**Browsers only allow camera and location on `https://` (or `http://localhost`).** For staff to check in from their
phones the site must be served over HTTPS.

Roles: admin (everything) · hr (people, leave, recruitment) · supervisor (attendance, work orders, leads) · employee (own portal).

Photos in `static/img` are from Unsplash (free licence).
