from flask import Flask, render_template, session, redirect, url_for, request, flash
from auth import auth
from database import get_db

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change this for security
app.register_blueprint(auth, url_prefix="/auth")

@app.route("/")
def home():
    return redirect(url_for("auth.login"))  # Redirect to login page


# Profile Page
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    db = get_db()
    cur = db.cursor()

    # Fetch profile details
    cur.execute("SELECT * FROM profiles WHERE user_id = %s", (user_id,))
    profile = cur.fetchone()

    # If profile does not exist, create a blank profile
    if not profile:
        cur.execute("INSERT INTO profiles (user_id, bio, interests) VALUES (%s, '', '')", (user_id,))
        db.commit()

    if request.method == "POST":
        bio = request.form["bio"]
        interests = request.form["interests"]

        cur.execute("UPDATE profiles SET bio = %s, interests = %s WHERE user_id = %s",
                    (bio, interests, user_id))
        db.commit()
        flash("Profile updated successfully!", "success")

        # ✅ Fetch the updated profile after saving changes
        cur.execute("SELECT * FROM profiles WHERE user_id = %s", (user_id,))
        profile = cur.fetchone()

    cur.close()
    db.close()
    return render_template("profile.html", profile=profile)



# Recommendation Page (Finding Similar Users)
@app.route("/recommendations")
def recommendations():
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    db = get_db()
    cur = db.cursor()

    # Get current user's interests
    cur.execute("SELECT interests FROM profiles WHERE user_id = %s", (user_id,))
    user_interests = cur.fetchone()

    if not user_interests or not user_interests["interests"]:
        flash("Update your interests to get recommendations.", "info")
        return redirect(url_for("profile"))

    user_interests = user_interests["interests"].replace(" ", "").split(",")  # Remove spaces and split

    # Create a REGEXP pattern to match interests properly
    regex_pattern = "|".join(user_interests)

    # Find users with at least one matching interest (excluding self)
    cur.execute("""
        SELECT users.id, users.username, users.email, profiles.bio, profiles.interests 
        FROM users 
        JOIN profiles ON users.id = profiles.user_id 
        WHERE users.id != %s AND REPLACE(profiles.interests, ' ', '') REGEXP %s
    """, (user_id, regex_pattern))

    recommendations = cur.fetchall()
    cur.close()
    db.close()

    return render_template("recommendations.html", users=recommendations)  # ✅ Fix variable name




if __name__ == "__main__":
    app.run(debug=True)
