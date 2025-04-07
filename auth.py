from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
import MySQLdb
from functools import wraps

auth = Blueprint("auth", __name__)


@auth.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        db = get_db()
        cur = db.cursor()

        try:
            cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                        (username, email, hashed_password))
            db.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("auth.login"))
        except MySQLdb.IntegrityError:
            flash("Email already registered.", "danger")
        finally:
            cur.close()
            db.close()

    return render_template("signup.html")



@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            cur.close()
            db.close()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["email"] = user["email"]
                flash("Login successful!", "success")
                return redirect(url_for("profile"))
            else:
                flash("Invalid email or password.", "danger")

    return render_template("login.html")



@auth.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))

# Authentication check decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("You need to log in first.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

@auth.route("/delete_account", methods=["POST"])
@login_required
def delete_account():
    user_id = session.get("user_id")

    if not user_id:
        flash("Unauthorized request.", "danger")
        return redirect(url_for("auth.login"))

    db = get_db()
    cur = db.cursor()

    try:
        # Delete user from the database
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        db.commit()
        
        # Clear session after account deletion
        session.clear()
        flash("Your account has been permanently deleted.", "success")
    except MySQLdb.Error as e:
        flash("An error occurred while deleting your account. Please try again.", "danger")
        print("Error:", e)
    finally:
        cur.close()
        db.close()

    return redirect(url_for("auth.signup"))
