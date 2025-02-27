from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
import MySQLdb

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
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
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
