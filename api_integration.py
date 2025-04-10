import requests

# API Keys (Use your actual API key here)
NEWS_API_KEY = "ca6168f3fc5548d1bd0044c3a102015e"

# Fetch Latest Tech News
def fetch_news():
    url = f"https://newsapi.org/v2/top-headlines?category=technology&apiKey={NEWS_API_KEY}"
    response = requests.get(url).json()
    articles = response.get("articles", [])
    
    if not articles:
        return ["⚠️ No news articles found."]
    
    news_list = []
    for article in articles[:5]:
        title = article["title"]
        source = article["source"]["name"]
        url = article["url"]
        news_list.append(f"📰 **{title}**\n📌 _{source}_\n🔗 [Read more]({url})\n\n")

    return news_list

# Fetch Latest Developer & Freelancing Jobs
def fetch_dev_jobs():
    url = "https://remoteok.io/api"  # Public API for remote jobs (no API key required)
    response = requests.get(url).json()
    
    if not isinstance(response, list) or len(response) < 2:
        return ["⚠️ No job listings found."]
    
    jobs_list = []
    for job in response[1:6]:  # Skip the first item (metadata)
        title = job.get("position", "Unknown Position")
        company = job.get("company", "Unknown Company")
        url = job.get("url", "#")
        location = job.get("location", "Remote")  # Most jobs on RemoteOK are remote

        jobs_list.append(f"💼 **{title}** at _{company}_\n📍 {location}\n🔗 [Apply Here]({url})\n\n")

    return jobs_list

# Fetch GitHub Trending Repositories
def fetch_github_trending():
    url = "https://api.github.com/search/repositories?q=stars:>1000&sort=stars"
    response = requests.get(url).json()
    repos = response.get("items", [])
    
    if not repos:
        return ["⚠️ No trending repositories found."]
    
    github_list = []
    for repo in repos[:5]:
        name = repo["name"]
        url = repo["html_url"]
        stars = repo["stargazers_count"]
        description = repo["description"] if repo["description"] else "No description available."
        
        github_list.append(f"🌟 **{name}**\n📜 {description}\n⭐ {stars} stars\n🔗 [View on GitHub]({url})\n\n")
    
    return github_list
