# HomeServiceHub — Online Home Service Booking and Billing System

A college major project built with Python Flask, HTML, CSS, JavaScript and SQLite.

## Features
- Responsive home page and service catalogue
- Search and category filter
- Session-based Add to Cart, quantity updates and remove option
- Checkout form with basic validation
- Booking confirmation and printable invoice (bill only; no online payment)
- Booking-status lookup by booking ID
- Admin login and dashboard
- Admin can add/edit services, enable/disable services and update booking status
- SQLite database is created and seeded automatically

## Requirements
- Python 3.10 or newer
- pip

## Run locally
1. Extract the ZIP.
2. Open a terminal in this folder.
3. (Optional) Create and activate a virtual environment:
   - Windows: `python -m venv .venv` then `.venv\\Scripts\\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Start the app: `python app.py`
6. Open `http://127.0.0.1:5000`

The database is created at `instance/home_service_hub.db` on first run.

## Demo administrator
- Username: `admin`
- Password: `admin123`

This is a classroom demo login only. Passwords are stored as plain text for simplicity, so do not deploy this version publicly. For real deployment, use password hashing, CSRF protection, secure session settings, access-controlled invoice URLs, HTTPS and proper environment secrets.

## Main routes
- `/` — Home
- `/services` — Service catalogue
- `/cart` — Cart
- `/checkout` — Booking checkout
- `/booking-status` — Find a booking by ID
- `/admin/login` — Admin login
- `/admin` — Dashboard
- `/admin/services` — Manage services
- `/admin/bookings` — Manage bookings

## Notes
- Prices are demo values in INR.
- Payment is not collected online. The app generates a bill only.
- Tax is set to zero by default; change the calculation in `checkout()` if your project guide requires a tax rule.
- Before real use, replace the demo admin authentication and add production security controls.
