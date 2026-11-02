import os
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "home_service_hub.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-for-production")
app.config["DATABASE"] = DB_PATH

DEFAULT_SERVICES = [
    ("Electrician Visit", "Electrical", "Electrical repairs, switches, fans and minor wiring checks.", 499),
    ("Plumbing Repair", "Plumbing", "Tap leaks, pipe repairs and basic plumbing assistance.", 399),
    ("Home Deep Cleaning", "Cleaning", "Room, kitchen and bathroom deep-cleaning service.", 1499),
    ("AC General Service", "Appliance Repair", "Basic AC inspection and general servicing.", 799),
    ("Carpentry Repair", "Carpentry", "Door hinges, shelves and small furniture repairs.", 599),
    ("Pest Control Visit", "Pest Control", "Inspection and standard home pest-control treatment.", 999),
]

def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        price REAL NOT NULL CHECK(price >= 0),
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        service_date TEXT NOT NULL,
        time_slot TEXT NOT NULL,
        notes TEXT DEFAULT '',
        subtotal REAL NOT NULL,
        tax REAL NOT NULL DEFAULT 0,
        total REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS booking_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
        service_id INTEGER,
        service_name TEXT NOT NULL,
        unit_price REAL NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        line_total REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    """)
    count = db.execute("SELECT COUNT(*) FROM services").fetchone()[0]
    if count == 0:
        db.executemany(
            "INSERT INTO services(name, category, description, price) VALUES(?,?,?,?)",
            DEFAULT_SERVICES
        )
    # Demo-only credentials for a local college project. Change before deployment.
    if db.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0] == 0:
        db.execute("INSERT INTO admin_users(username, password) VALUES(?,?)", ("admin", "admin123"))
    db.commit()
    db.close()

@app.before_request
def ensure_db():
    if not os.path.exists(DB_PATH):
        init_db()

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Please log in as an administrator.", "warning")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped

def get_cart():
    return session.setdefault("cart", {})

def cart_details():
    cart = session.get("cart", {})
    if not cart:
        return [], 0
    ids = [int(k) for k, v in cart.items() if int(v) > 0]
    if not ids:
        return [], 0
    placeholders = ",".join("?" for _ in ids)
    services = get_db().execute(
        f"SELECT * FROM services WHERE active=1 AND id IN ({placeholders})", ids
    ).fetchall()
    items, total = [], 0
    for service in services:
        qty = max(1, min(20, int(cart.get(str(service["id"]), 1))))
        line_total = service["price"] * qty
        items.append({"service": service, "quantity": qty, "line_total": line_total})
        total += line_total
    return items, total

@app.template_filter("inr")
def inr(value):
    return "₹{:,.2f}".format(float(value or 0))

@app.route("/")
def home():
    services = get_db().execute("SELECT * FROM services WHERE active=1 ORDER BY id DESC LIMIT 6").fetchall()
    return render_template("index.html", services=services)

@app.route("/services")
def services():
    category = request.args.get("category", "").strip()
    search = request.args.get("q", "").strip()
    sql = "SELECT * FROM services WHERE active=1"
    params = []
    if category:
        sql += " AND category=?"
        params.append(category)
    if search:
        sql += " AND (name LIKE ? OR description LIKE ? OR category LIKE ?)"
        params.extend([f"%{search}%"] * 3)
    sql += " ORDER BY category, name"
    rows = get_db().execute(sql, params).fetchall()
    categories = get_db().execute("SELECT DISTINCT category FROM services WHERE active=1 ORDER BY category").fetchall()
    return render_template("services.html", services=rows, categories=categories, category=category, q=search)

@app.post("/cart/add/<int:service_id>")
def add_to_cart(service_id):
    service = get_db().execute("SELECT id FROM services WHERE id=? AND active=1", (service_id,)).fetchone()
    if not service:
        abort(404)
    cart = dict(session.get("cart", {}))
    key = str(service_id)
    cart[key] = min(20, int(cart.get(key, 0)) + 1)
    session["cart"] = cart
    flash("Service added to your cart.", "success")
    return redirect(request.referrer or url_for("services"))

@app.route("/cart", methods=["GET", "POST"])
def cart():
    if request.method == "POST":
        cart_data = {}
        for key, value in request.form.items():
            if key.startswith("qty_"):
                try:
                    qty = int(value)
                    service_id = key[4:]
                    if qty > 0:
                        cart_data[service_id] = min(20, qty)
                except (ValueError, TypeError):
                    continue
        session["cart"] = cart_data
        flash("Cart updated.", "success")
        return redirect(url_for("cart"))
    items, total = cart_details()
    return render_template("cart.html", items=items, total=total)

@app.post("/cart/remove/<int:service_id>")
def remove_from_cart(service_id):
    cart = dict(session.get("cart", {}))
    cart.pop(str(service_id), None)
    session["cart"] = cart
    flash("Service removed from cart.", "info")
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    items, subtotal = cart_details()
    if not items:
        flash("Your cart is empty. Please add a service first.", "warning")
        return redirect(url_for("services"))
    if request.method == "POST":
        name = request.form.get("customer_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        service_date = request.form.get("service_date", "").strip()
        time_slot = request.form.get("time_slot", "").strip()
        notes = request.form.get("notes", "").strip()
        errors = []
        if len(name) < 2: errors.append("Enter a valid full name.")
        if "@" not in email or "." not in email.split("@")[-1]: errors.append("Enter a valid email address.")
        if not phone.isdigit() or len(phone) != 10: errors.append("Enter a 10-digit mobile number.")
        if len(address) < 8: errors.append("Enter a complete service address.")
        try:
            requested_date = datetime.strptime(service_date, "%Y-%m-%d").date()
            if requested_date < datetime.now().date(): errors.append("Service date cannot be in the past.")
        except ValueError:
            errors.append("Choose a valid service date.")
        if not time_slot: errors.append("Choose a time slot.")
        if errors:
            for error in errors: flash(error, "danger")
            return render_template("checkout.html", items=items, subtotal=subtotal)
        db = get_db()
        cur = db.execute("""
            INSERT INTO bookings(customer_name,email,phone,address,service_date,time_slot,notes,subtotal,tax,total,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (name,email,phone,address,service_date,time_slot,notes,subtotal,0,subtotal,"Pending",datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        booking_id = cur.lastrowid
        for item in items:
            svc = item["service"]
            db.execute("""INSERT INTO booking_items(booking_id,service_id,service_name,unit_price,quantity,line_total)
                          VALUES(?,?,?,?,?,?)""",
                       (booking_id,svc["id"],svc["name"],svc["price"],item["quantity"],item["line_total"]))
        db.commit()
        session["cart"] = {}
        return redirect(url_for("invoice", booking_id=booking_id))
    return render_template("checkout.html", items=items, subtotal=subtotal)

@app.route("/invoice/<int:booking_id>")
def invoice(booking_id):
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    if not booking:
        abort(404)
    items = db.execute("SELECT * FROM booking_items WHERE booking_id=?", (booking_id,)).fetchall()
    # Demo project: invoice URL is a simple receipt reference; add authentication in production.
    return render_template("invoice.html", booking=booking, items=items)

@app.route("/booking-status")
def booking_status():
    booking_id = request.args.get("id", "").strip()
    booking = None
    if booking_id.isdigit():
        booking = get_db().execute("SELECT id,customer_name,service_date,time_slot,status,created_at FROM bookings WHERE id=?", (int(booking_id),)).fetchone()
    return render_template("booking_status.html", booking=booking, searched=bool(booking_id))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = get_db().execute("SELECT * FROM admin_users WHERE username=? AND password=?", (username,password)).fetchone()
        if admin:
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            flash("Welcome to the admin dashboard.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Incorrect username or password.", "danger")
    return render_template("admin_login.html")

@app.get("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        "services": db.execute("SELECT COUNT(*) FROM services WHERE active=1").fetchone()[0],
        "bookings": db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0],
        "pending": db.execute("SELECT COUNT(*) FROM bookings WHERE status='Pending'").fetchone()[0],
        "revenue": db.execute("SELECT COALESCE(SUM(total),0) FROM bookings WHERE status!='Cancelled'").fetchone()[0],
    }
    bookings = db.execute("SELECT * FROM bookings ORDER BY id DESC LIMIT 8").fetchall()
    return render_template("admin_dashboard.html", stats=stats, bookings=bookings)

@app.route("/admin/services", methods=["GET", "POST"])
@admin_required
def admin_services():
    db = get_db()
    if request.method == "POST":
        service_id = request.form.get("service_id", "").strip()
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        try:
            price = float(request.form.get("price", ""))
            if price < 0: raise ValueError()
        except ValueError:
            flash("Enter a valid non-negative price.", "danger")
            return redirect(url_for("admin_services"))
        if not name or not category or not description:
            flash("All service fields are required.", "danger")
            return redirect(url_for("admin_services"))
        if service_id:
            db.execute("UPDATE services SET name=?,category=?,description=?,price=? WHERE id=?",
                       (name,category,description,price,int(service_id)))
            flash("Service updated.", "success")
        else:
            db.execute("INSERT INTO services(name,category,description,price) VALUES(?,?,?,?)",
                       (name,category,description,price))
            flash("Service added.", "success")
        db.commit()
        return redirect(url_for("admin_services"))
    rows = db.execute("SELECT * FROM services ORDER BY id DESC").fetchall()
    edit_id = request.args.get("edit", "").strip()
    editing = db.execute("SELECT * FROM services WHERE id=?", (edit_id,)).fetchone() if edit_id.isdigit() else None
    return render_template("admin_services.html", services=rows, editing=editing)

@app.post("/admin/services/<int:service_id>/toggle")
@admin_required
def toggle_service(service_id):
    db = get_db()
    row = db.execute("SELECT active FROM services WHERE id=?", (service_id,)).fetchone()
    if not row: abort(404)
    db.execute("UPDATE services SET active=? WHERE id=?", (0 if row["active"] else 1, service_id))
    db.commit()
    flash("Service visibility updated.", "success")
    return redirect(url_for("admin_services"))

@app.route("/admin/bookings")
@admin_required
def admin_bookings():
    rows = get_db().execute("SELECT * FROM bookings ORDER BY id DESC").fetchall()
    return render_template("admin_bookings.html", bookings=rows)

@app.post("/admin/bookings/<int:booking_id>/status")
@admin_required
def update_booking_status(booking_id):
    status = request.form.get("status", "")
    allowed = {"Pending", "Confirmed", "Completed", "Cancelled"}
    if status not in allowed: abort(400)
    db = get_db()
    db.execute("UPDATE bookings SET status=? WHERE id=?", (status, booking_id))
    db.commit()
    flash("Booking status updated.", "success")
    return redirect(request.referrer or url_for("admin_bookings"))

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
