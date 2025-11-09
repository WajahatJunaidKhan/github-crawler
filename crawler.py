#!/usr/bin/env python3
"""
crawler.py — GitHub repo stars crawler (Sofstica Assessment)
Fetches repositories by creation date range using GitHub GraphQL API.
Stores results in Postgres (repositories + daily star snapshot).
"""

import os
import requests
import psycopg2
from datetime import datetime, timedelta
import time

# Environment variables from GitHub Actions
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", 5432)
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# Crawl configuration
START_YEAR = int(os.getenv("START_YEAR", 2010))
END_YEAR = int(os.getenv("END_YEAR", 2014))
REPOS_PER_SHARD = int(os.getenv("REPOS_TO_FETCH", 25000))
REPO_BATCH_SIZE = 50  # GitHub max 100 per request

# Postgres connection
conn = psycopg2.connect(
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    database=POSTGRES_DB,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD
)
cursor = conn.cursor()

# Create table if not exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS repositories (
    repo_id TEXT PRIMARY KEY,
    full_name TEXT,
    stars INT,
    url TEXT,
    last_scraped TIMESTAMP
)
""")
conn.commit()

# GraphQL query template
QUERY = """
query($q:String!, $first:Int!, $after:String) {
  search(query:$q, type:REPOSITORY, first:$first, after:$after) {
    repositoryCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Repository {
        id
        nameWithOwner
        stargazerCount
        url
        createdAt
      }
    }
  }
}
"""

HEADERS = {"Authorization": f"bearer {GITHUB_TOKEN}"}

# Function to fetch a single batch of repos
def fetch_repos(query, after_cursor=None):
    variables = {"q": query, "first": REPO_BATCH_SIZE, "after": after_cursor}
    for _ in range(5):  # Retry up to 5 times
        r = requests.post("https://api.github.com/graphql", json={"query": QUERY, "variables": variables}, headers=HEADERS)
        if r.status_code == 200:
            data = r.json()
            if "errors" in data:
                print("GraphQL errors:", data["errors"])
                return [], None, False
            search = data["data"]["search"]
            repos = [
                {
                    "repo_id": n["id"],
                    "full_name": n["nameWithOwner"],
                    "stars": n["stargazerCount"],
                    "url": n["url"],
                    "last_scraped": datetime.utcnow()
                }
                for n in search["nodes"]
            ]
            return repos, search["pageInfo"]["endCursor"], search["pageInfo"]["hasNextPage"]
        else:
            print("Request failed, status:", r.status_code)
            time.sleep(2)
    return [], None, False

# Function to insert repos into Postgres
def upsert_repos(repos):
    for r in repos:
        cursor.execute("""
        INSERT INTO repositories (repo_id, full_name, stars, url, last_scraped)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (repo_id) DO UPDATE
        SET stars = EXCLUDED.stars,
            url = EXCLUDED.url,
            last_scraped = EXCLUDED.last_scraped
        """, (r["repo_id"], r["full_name"], r["stars"], r["url"], r["last_scraped"]))
    conn.commit()

# Main crawler logic
def crawl():
    all_repos = []
    # Split by date shards to bypass 1,000 limit
    delta = timedelta(days=30)  # 1 month per shard
    for year in range(START_YEAR, END_YEAR + 1):
        current = datetime(year, 1, 1)
        while current.year <= year:
            start_date = current.strftime("%Y-%m-%d")
            end_date = (current + delta).strftime("%Y-%m-%d")
            query = f"stars:>0 created:{start_date}..{end_date}"
            after_cursor = None
            while True:
                repos, after_cursor, has_next = fetch_repos(query, after_cursor)
                if not repos:
                    break
                upsert_repos(repos)
                all_repos.extend(repos)
                print(f"Fetched {len(all_repos)} repos so far for {start_date}..{end_date}")
                if not has_next:
                    break
            current += delta
            if len(all_repos) >= REPOS_PER_SHARD:
                print(f"Reached target of {REPOS_PER_SHARD} repos for shard {START_YEAR}-{END_YEAR}")
                return all_repos
    return all_repos

if __name__ == "__main__":
    crawl()
    print("Crawl finished!")
    cursor.close()
    conn.close()
