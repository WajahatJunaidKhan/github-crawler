#!/usr/bin/env python3
"""
crawler.py — GitHub repo stars crawler (Sofstica Assessment)
Fetches repositories by creation date range using GitHub GraphQL API.
Stores results in Postgres (repositories + daily star snapshot).
"""

import os
import time
import json
from datetime import datetime, timedelta
from dateutil.parser import parse as dtparse
import requests
import psycopg2
from psycopg2.extras import execute_values

# === Configuration ===
GITHUB_GRAPHQL = "https://api.github.com/graphql"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", 5432))
PG_DB = os.getenv("POSTGRES_DB", "postgres")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

REPOS_TO_FETCH = int(os.getenv("REPOS_TO_FETCH", "25000"))
PAGE_SIZE = 100
WINDOW_DAYS = int(os.getenv("CREATED_WINDOW_DAYS", "7"))
START_YEAR = int(os.getenv("START_YEAR", "2010"))
END_YEAR = int(os.getenv("END_YEAR", "2014"))

HEADERS = {
    "Authorization": f"bearer {GITHUB_TOKEN}" if GITHUB_TOKEN else "",
    "Accept": "application/vnd.github.v4+json",
    "User-Agent": "github-crawler"
}

QUERY = """
query($q:String!, $first:Int, $after:String) {
  rateLimit {
    cost
    remaining
    resetAt
  }
  search(query:$q, type:REPOSITORY, first:$first, after:$after) {
    repositoryCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Repository {
        id
        name
        url
        stargazerCount
        owner { login }
        createdAt
      }
    }
  }
}
"""


def graphql_request(payload):
    for attempt in range(6):
        r = requests.post(GITHUB_GRAPHQL, json=payload, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (502, 503, 504):
            wait = 2 ** attempt
            print(f"Transient {r.status_code}, wait {wait}s...")
            time.sleep(wait)
            continue
        print("GraphQL error:", r.status_code, r.text)
        r.raise_for_status()
    raise RuntimeError("GraphQL request failed after retries")

def connect_db():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )

def upsert_repos(conn, repos):
    sql = """
    INSERT INTO repositories (repo_id, full_name, name, owner_login, stars, url, metadata, last_scraped)
    VALUES %s
    ON CONFLICT (repo_id) DO UPDATE
      SET stars = EXCLUDED.stars,
          metadata = COALESCE(EXCLUDED.metadata, repositories.metadata),
          last_scraped = EXCLUDED.last_scraped;
    """
    vals = [(r['id'], r['full_name'], r['name'], r['owner'], r['stars'], r['url'],
             json.dumps(r['meta']), datetime.utcnow()) for r in repos]
    with conn.cursor() as cur:
        execute_values(cur, sql, vals, page_size=100)
    conn.commit()

def upsert_history(conn, rows):
    sql = """
    INSERT INTO repo_star_history (repo_id, stars, snapshot_at)
    VALUES %s
    ON CONFLICT (repo_id, snapshot_at) DO UPDATE SET stars = EXCLUDED.stars;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=100)
    conn.commit()

def crawl_range(conn, start_date, end_date):
    total = 0
    now = datetime.utcnow().date()
    current_start = start_date
    while current_start < end_date and total < REPOS_TO_FETCH:
        current_end = min(end_date, current_start + timedelta(days=WINDOW_DAYS))
        query_str = f"is:public created:{current_start}..{current_end}"
        cursor = None
        has_next = True

        while has_next and total < REPOS_TO_FETCH:
            vars = {"q": query_str, "first": PAGE_SIZE, "after": cursor}
            data = graphql_request({"query": QUERY, "variables": vars})
            if "errors" in data:
                print("GraphQL errors:", data["errors"])
                break

            rl = data["data"]["rateLimit"]
            remaining = rl["remaining"]
            resetAt = rl["resetAt"]
            print(f"Rate remaining {remaining}, reset at {resetAt}")
            if remaining < 50:
                reset_ts = dtparse(resetAt).timestamp()
                sleep_sec = max(1, int(reset_ts - time.time()) + 5)
                print(f"Rate limit low, sleeping {sleep_sec}s")
                time.sleep(sleep_sec)

            search = data["data"]["search"]
            repos = search["nodes"]
            cursor = search["pageInfo"]["endCursor"]
            has_next = search["pageInfo"]["hasNextPage"]

            mapped = []
            hist = []
            for r in repos:
                mapped.append({
                    "id": r["id"],
                    "name": r["name"],
                    "owner": r["owner"]["login"],
                    "full_name": f"{r['owner']['login']}/{r['name']}",
                    "stars": r["stargazerCount"],
                    "url": r["url"],
                    "meta": {"createdAt": r["createdAt"]}
                })
                hist.append((r["id"], r["stargazerCount"], now))
            if mapped:
                upsert_repos(conn, mapped)
                upsert_history(conn, hist)
                total += len(mapped)
                print(f"Fetched {len(mapped)} repos; total {total}")

            time.sleep(0.2)

        current_start = current_end + timedelta(days=1)

    print(f"Done: {total} repos from {start_date} to {end_date}")

def main():
    print(f"Starting crawl for {START_YEAR}-{END_YEAR}, target {REPOS_TO_FETCH}")
    conn = connect_db()
    start = datetime(START_YEAR, 1, 1).date()
    end = datetime(END_YEAR, 12, 31).date()
    crawl_range(conn, start, end)
    conn.close()

if __name__ == "__main__":
    main()
