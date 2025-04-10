from flask import Flask, render_template, session, redirect, url_for, request, flash, Blueprint, jsonify
from auth import auth
from database import get_db
from flask_socketio import SocketIO, emit, join_room, leave_room
from routes.messages import messages_bp, socketio
import os
from werkzeug.utils import secure_filename
from routes.spam_detection import init_spam_detection, spam_bp
from chatbot import get_response
from api_integration import fetch_news, fetch_dev_jobs, fetch_github_trending

# Correct initialization order
app = Flask(__name__)
app.secret_key = "8349fh79d98d39je"

# Initialize spam detection FIRST
init_spam_detection(app)

# Then initialize SocketIO
socketio.init_app(app)

# Register blueprints
# app.register_blueprint(spam_bp, url_prefix='/spam')
app.register_blueprint(spam_bp)
app.register_blueprint(auth)
app.register_blueprint(messages_bp)

# Configure upload folder and allowed extensions
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # Folder to store uploaded images
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}  # Allowed file extensions

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route("/")
def home():
    return redirect(url_for("auth.login"))  


# Own Profile Page
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    db = get_db()
    cur = db.cursor()

    # Fetch user profile details with all fields
    cur.execute("""
        SELECT users.username, profiles.* 
        FROM users 
        JOIN profiles ON users.id = profiles.user_id 
        WHERE users.id = %s
    """, (user_id,))
    profile = cur.fetchone()

    # Create profile if doesn't exist
    if not profile:
        cur.execute("""
            INSERT INTO profiles (
                user_id, bio, interests, education, experience, skills,
                current_position, organization, research_interests, publications,
                linkedin_url, github_url, website_url, profile_pic
            ) VALUES (%s, '', '', '', '', '', '', '', '', '', '', '', '', NULL)
        """, (user_id,))
        db.commit()
        # Refetch the newly created profile
        cur.execute("SELECT users.username, profiles.* FROM users JOIN profiles ON users.id = profiles.user_id WHERE users.id = %s", (user_id,))
        profile = cur.fetchone()

    # Handle profile update
    if request.method == "POST":
        # Get all form data
        bio = request.form.get("bio", "")
        interests = request.form.get("interests", "")
        education = request.form.get("education", "")
        experience = request.form.get("experience", "")
        skills = request.form.get("skills", "")
        current_position = request.form.get("current_position", "")
        organization = request.form.get("organization", "")
        research_interests = request.form.get("research_interests", "")
        publications = request.form.get("publications", "")
        linkedin_url = request.form.get("linkedin_url", "")
        github_url = request.form.get("github_url", "")
        website_url = request.form.get("website_url", "")

        # Handle profile picture upload
        profile_pic_path = None
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                profile_pic_path = os.path.join('uploads', filename).replace("\\", "/")

        # Update all profile fields
        update_query = """
            UPDATE profiles SET 
                bio = %s, 
                interests = %s,
                education = %s,
                experience = %s,
                skills = %s,
                current_position = %s,
                organization = %s,
                research_interests = %s,
                publications = %s,
                linkedin_url = %s,
                github_url = %s,
                website_url = %s
        """
        params = [
            bio, interests, education, experience, skills,
            current_position, organization, research_interests, publications,
            linkedin_url, github_url, website_url
        ]

        # Add profile pic to update if it was uploaded
        if profile_pic_path:
            update_query += ", profile_pic = %s"
            params.append(profile_pic_path)

        update_query += " WHERE user_id = %s"
        params.append(user_id)

        cur.execute(update_query, tuple(params))
        db.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    # Fetch pending connection requests and connections (existing code)
    cur.execute("""
        SELECT connections.id, users.username, users.email, connections.sender_id 
        FROM connections 
        JOIN users ON users.id = connections.sender_id 
        WHERE connections.receiver_id = %s AND connections.status = 'pending'
    """, (user_id,))
    friend_requests = cur.fetchall()

    cur.execute("""
        SELECT users.id, users.username 
        FROM connections 
        JOIN users ON users.id = CASE 
            WHEN connections.sender_id = %s THEN connections.receiver_id
            ELSE connections.sender_id 
        END
        WHERE (connections.sender_id = %s OR connections.receiver_id = %s) AND connections.status = 'accepted'
    """, (user_id, user_id, user_id))
    connections = cur.fetchall()

    cur.close()
    db.close()

    return render_template("profile.html", 
                         profile=profile, 
                         friend_requests=friend_requests, 
                         connections=connections, 
                         is_own_profile=True)


# Recommendations
@app.route("/recommendations")
def recommendations():
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    db = get_db()
    cur = db.cursor()


    cur.execute("SELECT interests FROM profiles WHERE user_id = %s", (user_id,))
    user_interests = cur.fetchone()

    if not user_interests or not user_interests["interests"]:
        flash("Update your interests to get recommendations.", "info")
        return redirect(url_for("profile"))

    user_interests = user_interests["interests"].replace(" ", "").split(",") 

    # Create a REGEXP pattern to match interests properly
    regex_pattern = "|".join(user_interests)

    
    cur.execute("""
        SELECT users.id, users.username, users.email, profiles.bio, profiles.interests, profiles.profile_pic
        FROM users 
        JOIN profiles ON users.id = profiles.user_id 
        WHERE users.id != %s AND REPLACE(profiles.interests, ' ', '') REGEXP %s
    """, (user_id, regex_pattern))

    recommendations = cur.fetchall()
    cur.close()
    db.close()

    return render_template("recommendations.html", users=recommendations)

# View Other Users' Profiles
@app.route("/profile/<int:user_id>")
def view_profile(user_id):
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    current_user_id = session["user_id"]
    db = get_db()
    cur = db.cursor()  # Using dictionary=True for easier access

    # Fetch the requested user's profile with ALL fields
    cur.execute("""
        SELECT 
            users.id,
            users.username, 
            profiles.bio,
            profiles.interests,
            profiles.profile_pic,
            profiles.education,
            profiles.experience,
            profiles.skills,
            profiles.current_position,
            profiles.organization,
            profiles.research_interests,
            profiles.publications,
            profiles.linkedin_url,
            profiles.github_url,
            profiles.website_url
        FROM users 
        JOIN profiles ON users.id = profiles.user_id 
        WHERE users.id = %s
    """, (user_id,))
    profile = cur.fetchone()

    if not profile:
        flash("Profile not found.", "danger")
        return redirect(url_for("profile"))

    # Check connection status between current user and viewed user
    cur.execute("""
        SELECT status 
        FROM connections 
        WHERE (sender_id = %s AND receiver_id = %s) 
           OR (sender_id = %s AND receiver_id = %s)
    """, (current_user_id, user_id, user_id, current_user_id))
    connection = cur.fetchone()
    
    connection_status = None
    if connection:
        connection_status = connection["status"]

    # Fetch the viewed user's connections count and list
    cur.execute("""
        SELECT users.id, users.username 
        FROM connections 
        JOIN users ON users.id = CASE 
            WHEN connections.sender_id = %s THEN connections.receiver_id
            ELSE connections.sender_id 
        END
        WHERE (connections.sender_id = %s OR connections.receiver_id = %s) 
        AND connections.status = 'accepted'
    """, (user_id, user_id, user_id))
    connections = cur.fetchall()

    cur.close()
    db.close()

    return render_template("profile.html", 
                         profile=profile, 
                         is_own_profile=False, 
                         connection_status=connection_status,
                         connections=connections)  # Pass connections to template


# send request 

@app.route("/send_request/<int:receiver_id>", methods=["POST"])
def send_request(receiver_id):
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    sender_id = session["user_id"]
    if sender_id == receiver_id:
        flash("You cannot connect with yourself.", "danger")
        return redirect(url_for("view_profile", user_id=receiver_id))

    db = get_db()
    cur = db.cursor()

    # Check if a connection already exists
    cur.execute("""
        SELECT status FROM connections 
        WHERE (sender_id = %s AND receiver_id = %s) 
        OR (sender_id = %s AND receiver_id = %s)
    """, (sender_id, receiver_id, receiver_id, sender_id))
    existing_request = cur.fetchone()

    if existing_request:
        flash("You already have a pending or accepted connection with this user!", "info")
    else:
        cur.execute("""
            INSERT INTO connections (sender_id, receiver_id, status) 
            VALUES (%s, %s, 'pending')
        """, (sender_id, receiver_id))
        db.commit()
        flash("Connection request sent!", "success")

    cur.close()
    db.close()
    return redirect(url_for("view_profile", user_id=receiver_id))


# accept or decline request

@app.route("/respond_request/<int:request_id>/<string:action>")
def respond_request(request_id, action):
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    db = get_db()
    cur = db.cursor()

    try:
        if action == "accept":
            cur.execute("UPDATE connections SET status = 'accepted' WHERE id = %s", (request_id,))
            flash("Connection accepted!", "success")
        elif action == "decline":
            cur.execute("DELETE FROM connections WHERE id = %s", (request_id,))
            flash("Connection declined!", "info")

        db.commit()
    except Exception as e:
        db.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        cur.close()
        db.close()

    return redirect(url_for("profile"))

# disconnect

@app.route("/disconnect/<int:user_id>", methods=["POST"])
def disconnect(user_id):
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    current_user_id = session["user_id"]

    db = get_db()
    cur = db.cursor()

    # Delete the connection from either direction
    cur.execute("""
        DELETE FROM connections 
        WHERE (sender_id = %s AND receiver_id = %s) 
        OR (sender_id = %s AND receiver_id = %s)
    """, (current_user_id, user_id, user_id, current_user_id))
    
    db.commit()
    cur.close()
    db.close()

    flash("You are no longer connected.", "info")
    return redirect(url_for("view_profile", user_id=user_id))

@app.route("/remove_profile_pic", methods=["POST"])
def remove_profile_pic():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Please log in first."})

    user_id = session["user_id"]
    db = get_db()
    cur = db.cursor()

    try:
        # Set profile_pic to NULL in the database
        cur.execute("UPDATE profiles SET profile_pic = NULL WHERE user_id = %s", (user_id,))
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": str(e)})
    finally:
        cur.close()
        db.close()

@app.route("/search_users")
def search_users():
    if "user_id" not in session:
        return jsonify({"error": "Please log in first."})

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Please enter a search term."})

    db = get_db()
    cur = db.cursor()

    # Search for users by username or email
    cur.execute("""
        SELECT users.id, users.username, users.email, profiles.bio, profiles.profile_pic 
        FROM users 
        JOIN profiles ON users.id = profiles.user_id 
        WHERE users.username LIKE %s OR users.email LIKE %s
        LIMIT 10
    """, (f"%{query}%", f"%{query}%"))

    users = cur.fetchall()
    cur.close()
    db.close()

    # Convert the result to a list of dictionaries
    users_list = []
    for user in users:
        users_list.append({
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "bio": user["bio"],
            "profile_pic": user["profile_pic"]
        })

    return jsonify(users_list)

@app.route("/chatbot", methods=['GET'])
def chatbot():
    return render_template("chatbot.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    bot_response = get_response(user_input)
    return jsonify({"response": bot_response})

@app.route("/news")
def news():
    return jsonify(fetch_news())

@app.route("/jobs")
def jobs():
    return jsonify(fetch_dev_jobs())

@app.route("/github")
def github():
    return jsonify(fetch_github_trending())

if __name__ == "__main__":
    socketio.run(app, debug=True)
