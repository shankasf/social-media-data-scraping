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
# Video query endpoint – removed invalid fields.
VIDEO_QUERY_URL = "https://open.tiktokapis.com/v2/research/video/query/?fields=id,like_count,comment_count,share_count"
USER_INFO_URL = "https://open.tiktokapis.com/v2/research/user/info/?fields=display_name,bio_description,avatar_url,is_verified,follower_count,following_count,likes_count,video_count"
# Comments endpoint with desired fields.
COMMENTS_URL = "https://open.tiktokapis.com/v2/research/video/comment/list/?fields=id,text,like_count,reply_count,parent_comment_id,create_time"

# Base output directory.
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
        if response.status_code == 200:
            token_data = response.json()
            token_file = os.path.join(BASE_OUTPUT_DIR, "access_token.json")
            await save_json(token_file, token_data)
            if "access_token" in token_data:
                print("Access Token:", token_data["access_token"])
                print("Expires In:", token_data["expires_in"], "seconds")
                print("Token Type:", token_data["token_type"])
                return token_data["access_token"]
            else:
                print("Error: No access token in response:", token_data)
        else:
            print("Error fetching access token:", response.status_code, response.text)
    return None

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

async def query_all_videos_for_username(access_token: str, username: str, overall_start: datetime, overall_end: datetime) -> dict:
    headers = {
        "authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    all_videos = []
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
            current_start = current_end + timedelta(days=1)
    return {"videos": all_videos}

async def query_video_comments(access_token: str, video_id: int, max_count: int = 50) -> dict:
    headers = {
        "authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "video_id": video_id,
        "max_count": max_count,
        "cursor": 0
    }
    all_comments = []
    has_more = True
    cursor = 0
    async with httpx.AsyncClient() as client:
        while has_more:
            payload["cursor"] = cursor
            response = await client.post(COMMENTS_URL, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                if "data" in data and "comments" in data["data"]:
                    comments = data["data"]["comments"]
                    all_comments.extend(comments)
                    has_more = data["data"].get("has_more", False)
                    cursor = data["data"].get("cursor", 0)
                    print(f"Fetched {len(comments)} comments for video {video_id}; total so far: {len(all_comments)}")
                else:
                    print("No comment data found for video", video_id, ":", data)
                    break
            else:
                print("Error querying video comments:", response.status_code, response.text)
                break
    return {"comments": all_comments}

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

    # Set the overall date range to January 1, 2024 to February 20, 2025.
    overall_start = datetime(2024, 1, 1)
    overall_end = datetime(2025, 2, 20)

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
        
        if "videos" in videos_data:
            comments_dir = os.path.join(user_dir, "comments")
            os.makedirs(comments_dir, exist_ok=True)
            for video in videos_data["videos"]:
                video_id = video.get("id")
                if video_id:
                    print(f"Querying comments for video id: {video_id}")
                    comments_data = await query_video_comments(access_token, video_id, max_count=50)
                    comments_file = os.path.join(comments_dir, f"comments_{video_id}.json")
                    await save_json(comments_file, comments_data)
                    
        print(f"Finished processing {username}.\n")

if __name__ == "__main__":
    asyncio.run(main())
