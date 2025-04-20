from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
import MySQLdb
from functools import wraps
from google.oauth2 import id_token
from google.auth.transport import requests
import os

auth = Blueprint("auth", __name__)

# Google OAuth Config
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', 'YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com')

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

@auth.route("/google-auth", methods=["POST"])
def google_auth():
    if request.method == "POST":
        token = request.json.get('credential')
        csrf_token = request.json.get('g_csrf_token')
        
        if not token:
            return jsonify({'success': False, 'message': 'No credential token provided'}), 400
        
        try:
            # Verify the Google ID token
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
            
            # Check that the token is valid for our client
            if idinfo['aud'] != GOOGLE_CLIENT_ID:
                raise ValueError('Invalid client ID')
            
            # Get user info from Google
            email = idinfo['email']
            name = idinfo.get('name', 'User')
            google_id = idinfo['sub']
            
            db = get_db()
            cur = db.cursor()
            
            try:
                # Check if user exists
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cur.fetchone()
                
                if user:
                    # User exists, log them in
                    session["user_id"] = user["id"]
                    session["username"] = user["username"]
                    session["email"] = user["email"]
                    return jsonify({
                        'success': True,
                        'redirect': url_for('profile')
                    })
                else:
                    # Create new user
                    username = email.split('@')[0]  # Use email prefix as username
                    
                    # Check if username exists, append numbers if needed
                    counter = 1
                    original_username = username
                    while True:
                        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                        if not cur.fetchone():
                            break
                        username = f"{original_username}{counter}"
                        counter += 1
                    
                    # Insert new user with NULL password (Google-authenticated users don't need one)
                    cur.execute(
                        "INSERT INTO users (username, email, google_id) VALUES (%s, %s, %s)",
                        (username, email, google_id)
                    )
                    db.commit()
                    
                    # Get the new user's ID
                    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                    user_id = cur.fetchone()["id"]
                    
                    # Set session
                    session["user_id"] = user_id
                    session["username"] = username
                    session["email"] = email
                    
                    return jsonify({
                        'success': True,
                        'redirect': url_for('profile')
                    })
                    
            except MySQLdb.Error as e:
                db.rollback()
                return jsonify({
                    'success': False,
                    'message': 'Database error during authentication'
                }), 500
                
            finally:
                cur.close()
                db.close()
                
        except ValueError as e:
            # Invalid token
            return jsonify({
                'success': False,
                'message': 'Invalid authentication token'
            }), 401
