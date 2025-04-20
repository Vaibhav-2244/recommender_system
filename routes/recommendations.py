from flask import Blueprint, session, redirect, url_for, render_template, flash
from database import get_db
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

recommendations_bp = Blueprint('recommendations', __name__)

def preprocess_text(text):
    """Preprocess text by removing special characters and converting to lowercase"""
    if not text:
        return ""
    return re.sub(r'[^\w\s]', '', text.lower())

def calculate_similarity(user_profile, other_profiles):
    """Calculate similarity scores between user profile and other profiles"""
    # Combine relevant fields for similarity calculation
    user_text = ' '.join([
        user_profile['interests'] or '',
        user_profile['education'] or '',
        user_profile['experience'] or '',
        user_profile['skills'] or '',
        user_profile['current_position'] or '',
        user_profile['organization'] or '',
        user_profile['research_interests'] or '',
        user_profile['publications'] or ''
    ])
    
    other_texts = []
    for profile in other_profiles:
        text = ' '.join([
            profile['interests'] or '',
            profile['education'] or '',
            profile['experience'] or '',
            profile['skills'] or '',
            profile['current_position'] or '',
            profile['organization'] or '',
            profile['research_interests'] or '',
            profile['publications'] or ''
        ])
        other_texts.append(text)
    
    # Preprocess all texts
    user_text = preprocess_text(user_text)
    other_texts = [preprocess_text(text) for text in other_texts]
    
    # Create TF-IDF vectors
    vectorizer = TfidfVectorizer()
    all_texts = [user_text] + other_texts
    tfidf_matrix = vectorizer.fit_transform(all_texts)
    
    # Calculate cosine similarity
    similarity_scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    
    return similarity_scores

def get_connection_network(user_id, db):
    """Get the network of connections for a user"""
    cur = db.cursor()
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
    return {row['id'] for row in cur.fetchall()}

@recommendations_bp.route("/recommendations")
def recommendations():
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    db = get_db()
    cur = db.cursor()

    # Get user's profile
    cur.execute("""
        SELECT * FROM profiles WHERE user_id = %s
    """, (user_id,))
    user_profile = cur.fetchone()

    if not user_profile:
        flash("Please complete your profile to get recommendations.", "info")
        return redirect(url_for("profile"))

    # Get all other profiles except user's own and their connections
    connection_network = get_connection_network(user_id, db)
    cur.execute("""
        SELECT users.id, users.username, users.email, profiles.*
        FROM users 
        JOIN profiles ON users.id = profiles.user_id 
        WHERE users.id != %s
    """, (user_id,))
    other_profiles = cur.fetchall()

    # Filter out existing connections
    other_profiles = [p for p in other_profiles if p['id'] not in connection_network]

    if not other_profiles:
        flash("No new recommendations available at the moment.", "info")
        return render_template("recommendations.html", users=[])

    # Calculate similarity scores
    similarity_scores = calculate_similarity(user_profile, other_profiles)

    # Combine profiles with their similarity scores
    scored_profiles = list(zip(other_profiles, similarity_scores))
    
    # Sort by similarity score in descending order
    scored_profiles.sort(key=lambda x: x[1], reverse=True)
    
    # Get top 10 recommendations
    top_recommendations = [profile for profile, _ in scored_profiles[:10]]

    cur.close()
    db.close()

    return render_template("recommendations.html", users=top_recommendations) 