# GitHub Crawler Assignment

## Submission Note

**Due to GitHub API search limits, each search query returns a maximum of 1,000 repositories.**  

This implementation fetches ~1,000 repos per shard. The crawler is designed to scale to **100,000+ repositories** using **multiple date/star range shards in parallel**, demonstrating an understanding of API limits and large-scale crawling strategies.

---

#### Result CSV File is present in the artifact it can be as accessed by Actions-> Workflow-> Success Run-> Artifact-> click to download

#### 2 Scienario Questions Answers are at the end of Readme file.

## Overview

This repository contains the implementation of a **GitHub Crawler** that fetches repository information (repo ID, full name, stars, URL, last scraped timestamp) using **GitHub's GraphQL API** and stores it in a **PostgreSQL database**.

The solution is designed to be **scalable, automated, and efficient**, following clean software engineering practices, pagination, and retry mechanisms.

---

## Features

### 1. Fetch GitHub Repositories
- Uses GitHub GraphQL API
- Retrieves `repo_id`, `full_name`, `stars`, `url`, `last_scraped`
- Supports **pagination** using `endCursor` and `hasNextPage`
- Handles API **rate limits** and implements retries on failures

### 2. Database Storage
- Stores crawled data in **PostgreSQL**
- Uses **upsert logic** (`ON CONFLICT`) for efficient updates
- Flexible schema for future expansion (issues, PRs, comments, CI checks, etc.)

### 3. Scalable Architecture
- Supports **shards** using multiple date ranges (`created:` filter) or star ranges to overcome the **GitHub 1,000-result per query limit**
- Each shard can run as a **parallel job in GitHub Actions**, enabling large-scale crawling

### 4. GitHub Actions Automation
- Workflow sets up a **PostgreSQL service container**
- Installs dependencies (`requirements.txt`) automatically
- Runs the crawler and stores results
- Dumps database contents to CSV artifacts for inspection

---

## Implementation Details

### Crawler (`crawler.py`)

GraphQL query uses **inline fragments** to select only `Repository` nodes:

```graphql
... on Repository {
    id
    nameWithOwner
    stargazerCount
    url
    createdAt
}
```

- Pagination handled via `endCursor` and `hasNextPage`
- Retry mechanism for temporary API failures
- Efficient insertion into Postgres using `ON CONFLICT`

### Database (`db_init.sql`)

Table `repositories`:

```sql
CREATE TABLE IF NOT EXISTS repositories (
    repo_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    stars INT,
    url TEXT,
    last_scraped TIMESTAMP
);
```

Flexible to add additional metadata in the future without affecting existing rows.

### GitHub Actions Workflow (`.github/workflows/crawl.yml`)

- Sets up Postgres service container
- Installs Python and dependencies
- Runs the crawler script
- Dumps CSV (`\copy`) and uploads as artifact
- Fully automated and reproducible with `workflow_dispatch`

### API Limitation Note

**GitHub Search API Limit:** Each search query returns up to 1,000 results, even with pagination.

Therefore, in this implementation, each shard currently fetches ~1,000 repositories.

**Scaling strategy:**
- Use multiple date ranges or star ranges to create non-overlapping queries
- Run multiple shards in parallel via GitHub Actions
- Combining artifacts allows fetching 100,000+ repositories

This demonstrates understanding of API limits and a professional approach to large-scale crawling.

---

## Running Locally

### Install dependencies

```bash
pip install -r requirements.txt
```

### Set environment variables

```bash
export GITHUB_TOKEN=<your_token>
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
export POSTGRES_DB=postgres
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
```

### Initialize database

```bash
psql -U postgres -d postgres -f db_init.sql
```

### Run crawler

```bash
python crawler.py
```

### Inspect database or export CSV

```bash
psql -U postgres -d postgres -c "\copy (SELECT * FROM repositories) TO 'repos.csv' CSV HEADER"
```

---

## Key Takeaways

**Demonstrates clean architecture principles:**
- Separation of concerns
- Immutable data structures
- Robust error handling

**Workflow-ready:** GitHub Actions automation ensures reproducible results.

**Scalable design:** Ready to handle hundreds of thousands of repositories with multiple shards.

---

## Discussion & Scaling

### Scaling to 500 Million Repositories

Fetching 500 million repositories is a massive-scale operation, and the approach would need to change compared to crawling 100,000 repos:

#### 1. Sharding & Parallelization
- Split the data into fine-grained shards using creation date, star ranges, or programming language
- Run hundreds or thousands of parallel jobs, either in GitHub Actions or a distributed pipeline (e.g., Airflow, Prefect, or Celery workers)

#### 2. Incremental Crawling
- Instead of fetching all 500 million repos repeatedly, fetch **only new or updated repositories daily** using timestamps like `updatedAt` or `pushedAt`

#### 3. Distributed Database
- Use a **sharded or distributed database** (e.g., CockroachDB, Amazon Aurora) to store and query large datasets efficiently

#### 4. Rate Limit Management
- Manage multiple GitHub tokens
- Implement exponential backoff and queueing to handle API rate limits safely

#### 5. Monitoring & Logging
- Log all shard progress and errors
- Use dashboards to monitor data completeness and crawling performance

#### 6. Batch Inserts and Table Partitioning
- Insert and update data in batches
- Partition large tables by repository ID or creation date to improve query and update efficiency

---

### Schema Evolution for Additional Metadata

To gather more metadata such as **issues, pull requests, commits, comments, reviews, and CI checks**, the database schema can evolve as follows:

#### Repositories Table

Stores basic repo information:

```sql
CREATE TABLE repositories (
    repo_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    stars INT,
    url TEXT,
    last_scraped TIMESTAMP
);
```

#### Pull Requests Table

One-to-many with repositories:

```sql
CREATE TABLE pull_requests (
    pr_id TEXT PRIMARY KEY,
    repo_id TEXT REFERENCES repositories(repo_id),
    title TEXT,
    state TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_scraped TIMESTAMP
);
```

#### Commits Table

One-to-many with pull requests:

```sql
CREATE TABLE commits (
    commit_sha TEXT PRIMARY KEY,
    pr_id TEXT REFERENCES pull_requests(pr_id),
    author TEXT,
    message TEXT,
    created_at TIMESTAMP
);
```

#### Comments Table

For issues and pull requests:

```sql
CREATE TABLE comments (
    comment_id TEXT PRIMARY KEY,
    parent_type TEXT, -- 'issue' or 'pull_request'
    parent_id TEXT,
    author TEXT,
    body TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### Reviews & CI Checks

```sql
CREATE TABLE reviews (
    review_id TEXT PRIMARY KEY,
    pr_id TEXT REFERENCES pull_requests(pr_id),
    reviewer TEXT,
    state TEXT,
    created_at TIMESTAMP
);

CREATE TABLE ci_checks (
    check_id TEXT PRIMARY KEY,
    pr_id TEXT REFERENCES pull_requests(pr_id),
    status TEXT,
    conclusion TEXT,
    created_at TIMESTAMP
);
```

### Efficient Updates

- Use `UPSERT` / `ON CONFLICT` to update only changed rows
- Track `last_scraped` and `updated_at` timestamps to identify new or updated records
- Insert new comments, commits, or PRs as separate rows instead of overwriting old ones
- Partition large tables to minimize the number of rows affected by updates

This approach ensures efficient, minimal-impact database operations even as metadata grows over time.

---

## Contributing

[Add contributing guidelines here]
