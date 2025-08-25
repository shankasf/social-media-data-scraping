# Social media Data Scraper

This project uses the **TikTok Research API (v2)** to collect structured data about users, their videos, and associated comments.
It is built with **async Python (httpx + asyncio)** for efficient non-blocking requests, and saves all results as JSON files organized by user and video.

---

## Features

* Authenticates with TikTok API using **client credentials**.
* Extracts **user information** (profile details, follower/following counts, etc.).
* Fetches **all videos** by a user within a given date range (chunked into 30-day intervals).
* Collects **video metadata** (likes, comments count, shares, etc.).
* Scrapes **video comments** (with pagination support).
* Saves all results into **structured folders** under `scraped_data/`.

---

## Project Structure

Example output layout:

```
scraped_data/
  ├── access_token.json
  ├── kamalaharris/
  │     ├── user_info.json
  │     ├── video_12345/
  │     │     ├── video_details.json
  │     │     └── comments/
  │     │           └── comments.json
  └── realdonaldtrump/
        ├── user_info.json
        ├── video_67890/
              ├── video_details.json
              └── comments/
                    └── comments.json
```

---

## Requirements

* Python 3.8+
* TikTok Research API client credentials

Install dependencies:

```bash
pip install httpx aiofiles
```

---

## Configuration

1. Set your TikTok API credentials in the script:

   ```python
   CLIENT_KEY = "your_client_key"
   CLIENT_SECRET = "your_client_secret"
   ```
2. Adjust `BASE_OUTPUT_DIR` if needed (default saves to `D:\Research emergency\tiktok\scraped_data`).
3. Update the `initial_profiles` list in `main()` with TikTok profile URLs to scrape.
4. Modify the date range:

   ```python
   overall_start = datetime(2024, 1, 1)
   overall_end = datetime(2025, 2, 20)
   ```

---

## Running the Script

Run with Python:

```bash
python tiktok_scraper.py
```

The script will:

1. Request an **access token**.
2. Loop through each profile in `initial_profiles`.
3. Query and save **user info**.
4. Query and save **videos** and their **comments**.

---

## Notes

* Large scraping jobs may take significant time due to API rate limits.
* Always comply with TikTok’s API Terms of Service and data use policies.
* If you want to scrape additional fields, extend the `VIDEO_QUERY_URL` or `COMMENTS_URL` fields list.

---

## Next Steps

* Add support for retries/backoff on rate-limiting.
* Parallelize scraping across multiple users.
* Integrate database storage (PostgreSQL / MongoDB) instead of JSON output.
