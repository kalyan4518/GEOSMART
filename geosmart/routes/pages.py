"""HTML page and session routes."""

from flask import flash, redirect, render_template, request, session, url_for

from geosmart.app_core import app
from geosmart.config import Config, ISSUE_TYPES
from geosmart.web_support import (
    _is_admin,
    _is_authenticated,
    _load_dashboard_carousel_images,
    require_auth,
)
@app.route("/")
def splash():
    return render_template("splash.html")


@app.route("/index")
def index_page():
    return render_template("index_page.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("login.html", login_mode="user")

        session["user"] = email
        session["role"] = "user"
        return redirect(url_for("dashboard"))
    return render_template("login.html", login_mode="user")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if Config.ADMIN_PASSWORD and email == Config.ADMIN_EMAIL and password == Config.ADMIN_PASSWORD:
            session["user"] = email
            session["role"] = "admin"
            return redirect(url_for("dashboard"))

        flash("Invalid admin credentials.", "error")
    return render_template("login.html", login_mode="admin")


@app.route("/demo-login/google")
def demo_google_login():
    session["user"] = "google.user@geosmart.local"
    session["role"] = "user"
    return redirect(url_for("dashboard"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        session["user"] = name or email or "User"
        session["role"] = "user"
        return redirect(url_for("dashboard"))
    return render_template("signup.html")


@app.route("/dashboard")
@require_auth()
def dashboard():
    user = session.get("user", "User")
    if _is_admin():
        return render_template("admin_dashboard.html", user=user, role="admin")
    carousel_images = _load_dashboard_carousel_images()
    return render_template("dashboard.html", user=user, role="user", carousel_images=carousel_images)


@app.route("/admin")
@require_auth(admin_only=True)
def admin_home():
    return redirect(url_for("dashboard"))


@app.route("/analyze")
@require_auth()
def analyze():
    return render_template("analyze.html")


@app.route("/complaint")
@require_auth()
def complaint():
    return render_template(
        "complaint.html",
        complaints=[],
        issue_types=ISSUE_TYPES,
        can_update_status=_is_admin(),
    )


@app.route("/municipal")
@require_auth()
def municipal():
    return render_template("municipal.html")


@app.route("/profile")
@require_auth()
def profile():
    return render_template("profile.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("splash"))

