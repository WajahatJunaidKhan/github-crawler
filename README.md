# GitHub Crawler Assignment 

## Submission Note
**Due to GitHub API search limits, each search query returns a maximum of 1,000 repositories.**  
This implementation fetches ~1,000 repos per shard. The crawler is designed to scale to **100,000+ repositories** using **multiple date/star range shards in parallel**, demonstrating an understanding of API limits and large-scale crawling strategies.

---

## Overview
This repository contains the implementation of a **GitHub Crawler** that fetches repository information (repo ID, full name, stars, URL, last scraped timestamp) using **GitHub's GraphQL API** and stores it in a **PostgreSQL database**.  

The solution is designed to be **scalable, automated, and efficient**, following clean software engineering practices, pagination, and retry mechanisms.

---

## Features

1. **Fetch GitHub Repositories**
   - Uses GitHub GraphQL API.
   - Retrieves `repo_id`, `full_name`, `stars`, `url`, `last_scraped`.
   - Supports **pagination** using `endCursor` and `hasNextPage`.
   - Handles API **rate limits** and implements retries on failures.

2. **Database Storage**
   - Stores crawled data in **PostgreSQL**.
   - Uses **upsert logic** (`ON CONFLICT`) for efficient updates.
   - Flexible schema for future expansion (issues, PRs, comments, CI checks, etc.).

3. **Scalable Architecture**
   - Supports **shards** using multiple date ranges (`created:` filter) or star ranges to overcome the **GitHub 1,000-result per query limit**.
   - Each shard can run as a **parallel job in GitHub Actions**, enabling large-scale crawling.

4. **GitHub Actions Automation**
   - Workflow sets up a **PostgreSQL service container**.
   - Installs dependencies (`requirements.txt`) automatically.
   - Runs the crawler and stores results.
   - Dumps database contents to CSV artifacts for inspection.

---

## Implementation Details

### Crawler (`crawler.py`)
- GraphQL query uses **inline fragments** to select only `Repository` nodes:
  ```graphql
  ... on Repository {
      id
      nameWithOwner
      stargazerCount
      url
      createdAt
  }
