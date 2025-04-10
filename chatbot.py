import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from api_integration import fetch_news, fetch_dev_jobs, fetch_github_trending

# Load dataset
df = pd.read_csv("cleaned_dataset.csv")

# TF-IDF Vectorizer
vectorizer = TfidfVectorizer()
tfidf_matrix = vectorizer.fit_transform(df["Question"])

def get_response(user_input):
    user_input = user_input.lower()

    # Check if the user is asking for tech news
    if "news" in user_input or "latest tech news" in user_input:
        news = fetch_news()
        return "\n".join(news) if news else "⚠️ Sorry, I couldn't fetch the news."

    # Check if the user is asking for freelancing or developer jobs
    elif "job" in user_input or "freelancing jobs" in user_input or "developer jobs" in user_input:
        jobs = fetch_dev_jobs()
        return "\n".join(jobs) if jobs else "⚠️ Sorry, I couldn't fetch job listings."

    # Check if the user is asking for GitHub trending projects
    elif "github" in user_input or "trending projects" in user_input or "popular repositories" in user_input:
        github_repos = fetch_github_trending()
        return "\n".join(github_repos) if github_repos else "⚠️ Sorry, I couldn't fetch GitHub trending repositories."

    # Otherwise, match with the dataset
    user_tfidf = vectorizer.transform([user_input])
    similarities = cosine_similarity(user_tfidf, tfidf_matrix)
    
    best_match_idx = similarities.argmax()
    confidence = similarities[0, best_match_idx]

    if confidence > 0.3:
        return df["Answer"].iloc[best_match_idx]
    else:
        return "I'm not sure. Please refine your query."
