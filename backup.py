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

    interests = user_interests["interests"]

    # Find users with similar interests
    cur.execute("SELECT users.id, users.username, profiles.bio, profiles.interests FROM users "
                "JOIN profiles ON users.id = profiles.user_id "
                "WHERE users.id != %s AND profiles.interests LIKE %s", 
                (user_id, f"%{interests}%"))

    recommendations = cur.fetchall()
    cur.close()
    db.close()

    return render_template("recommendations.html", recommendations=recommendations)