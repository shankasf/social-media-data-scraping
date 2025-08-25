import asyncio
import httpx
import json
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode
import aiofiles

# -------------------------
# Configuration & Endpoints
# -------------------------

CLIENT_KEY = "awzbf3ywv65u253d"
CLIENT_SECRET = "ZKXBkCpHtTG7sDBUhy0fIrqXmHZqMNC5"

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
VIDEO_QUERY_URL = "https://open.tiktokapis.com/v2/research/video/query/?fields=id,like_count,comment_count,share_count"
USER_INFO_URL = "https://open.tiktokapis.com/v2/research/user/info/?fields=display_name,bio_description,avatar_url,is_verified,follower_count,following_count,likes_count,video_count"

BASE_OUTPUT_DIR = r"D:\Research emergency\tiktok\scraped_data"
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

# -------------------------
# Helper Functions
# -------------------------

async def save_json(filename: str, data: dict):
    async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(data, indent=2, ensure_ascii=False))

def extract_username(profile_url: str) -> str:
    match = re.search(r"/@([^/?]+)", profile_url)
    return match.group(1) if match else profile_url

# -------------------------
# API Functions
# -------------------------

async def get_client_access_token() -> str:
    data = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient() as client:
        response = await client.post(TOKEN_URL, data=data, headers=headers)
        token_data = response.json()
        token_file = os.path.join(BASE_OUTPUT_DIR, "access_token.json")
        await save_json(token_file, token_data)
        if "access_token" in token_data:
            print("Access Token:", token_data["access_token"])
            return token_data["access_token"]
        else:
            print("Error: No access token in response:", token_data)
    return None

async def query_all_videos_for_username(access_token: str, username: str, overall_start: datetime, overall_end: datetime) -> dict:
    headers = {
        "authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    all_videos = []
    
    # Set maximum period of 30 days per query.
    max_interval = timedelta(days=30)
    current_start = overall_start
    async with httpx.AsyncClient() as client:
        while current_start <= overall_end:
            current_end = min(current_start + max_interval - timedelta(days=1), overall_end)
            payload = {
                "query": {
                    "and": [
                        {"operation": "EQ", "field_name": "username", "field_values": [username]}
                    ]
                },
                "start_date": current_start.strftime("%Y%m%d"),
                "end_date": current_end.strftime("%Y%m%d"),
                "max_count": 100
            }
            print(f"Querying videos from {payload['start_date']} to {payload['end_date']}")
            
            # Pagination variables for the current interval.
            has_more = True
            cursor = None
            search_id = None

            while has_more:
                if cursor is not None and search_id is not None:
                    payload["cursor"] = cursor
                    payload["search_id"] = search_id
                response = await client.post(VIDEO_QUERY_URL, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and "videos" in data["data"]:
                        videos = data["data"]["videos"]
                        all_videos.extend(videos)
                        print(f"Fetched {len(videos)} videos; total so far: {len(all_videos)}")
                        has_more = data["data"].get("has_more", False)
                        cursor = data["data"].get("cursor")
                        search_id = data["data"].get("search_id")
                    else:
                        print("No video data found in response for this interval:", data)
                        break
                else:
                    print("Error querying video data:", response.status_code, response.text)
                    break
            # Move to the next 30-day interval.
            current_start = current_end + timedelta(days=1)
    
    return {"videos": all_videos}

async def query_user_info(access_token: str, username: str) -> dict:
    headers = {
        "authorization": f"Bearer {access_token}",
        "Content-Type": "text/plain"
    }
    payload = {"username": username}
    async with httpx.AsyncClient() as client:
        response = await client.post(USER_INFO_URL, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            print("User Info Response:")
            print(json.dumps(data, indent=2))
            return data
        else:
            print("Error querying user info:", response.status_code, response.text)
            return {}

# -------------------------
# Main Workflow
# -------------------------

async def main():
    initial_profiles = [
        "https://www.tiktok.com/@kamalaharris",
        "https://www.tiktok.com/@realdonaldtrump"
    ]
    
    access_token = await get_client_access_token()
    if not access_token:
        print("Cannot continue without a valid access token.")
        return

    # Define the overall time period (for example, the whole year 2022)
    overall_start = datetime(2023, 1, 1)
    overall_end = datetime(2025, 2, 22)

    for profile_url in initial_profiles:
        username = extract_username(profile_url)
        print(f"Processing profile for username: {username}")
        user_dir = os.path.join(BASE_OUTPUT_DIR, username)
        os.makedirs(user_dir, exist_ok=True)
        
        user_info = await query_user_info(access_token, username)
        user_info_file = os.path.join(user_dir, "user_info.json")
        await save_json(user_info_file, user_info)
        
        videos_data = await query_all_videos_for_username(access_token, username, overall_start, overall_end)
        videos_file = os.path.join(user_dir, "all_videos.json")
        await save_json(videos_file, videos_data)
        
        print(f"Finished processing {username}.\n")

if __name__ == "__main__":
    asyncio.run(main())
