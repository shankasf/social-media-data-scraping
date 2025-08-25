import asyncio
import json
import os
import re
from datetime import datetime
from typing import List, Dict
from urllib.parse import urlencode

import aiofiles
import jmespath
from httpx import AsyncClient, Response
from loguru import logger as log
from parsel import Selector

# --- TikTok API & Scraping Constants ---
TIKTOK_API_BASE = "https://www.tiktok.com/api"
TOKEN_URL = "https://open-api.tiktok.com/oauth/access_token/"
MAX_RETRIES = 3
RETRY_DELAY = 2

# Replace with your actual TikTok API credentials.
CLIENT_KEY = "awzbf3ywv65u253d"
CLIENT_SECRET = "ZKXBkCpHtTG7sDBUhy0fIrqXmHZqMNC5"

# Initialize AsyncClient with common headers.
client = AsyncClient(
    http2=True,
    headers={
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept": ("text/html,application/xhtml+xml,application/xml;"
                   "q=0.9,image/webp,image/apng,*/*;q=0.8"),
        "Accept-Encoding": "gzip, deflate, br",
        # Initial cookie and referer may still be needed for some endpoints.
        "Cookie": "_ttp=2gjoMji3Lh9fBuFboIuRYaRuWsr; ...",  # Add valid TikTok cookies if required.
        "Referer": "https://www.tiktok.com/",
    },
    timeout=30.0,
    follow_redirects=True
)

# --- API Access Token Integration ---
async def get_client_access_token(client_key: str, client_secret: str) -> str:
    """
    Fetch the client access token from TikTok's API using your client credentials.
    The API expects the parameters: client_key, client_secret, and grant_type.
    """
    params = {
        "client_key": client_key,
        "client_secret": client_secret,
        "grant_type": "client_credential"
    }
    response = await client.get(TOKEN_URL, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to get access token: {response.status_code} {response.text}")

    result = response.json()
    if result.get("status_code") != 0:
        raise Exception(f"Error from API: {result.get('message')}")

    access_token = result.get("data", {}).get("access_token")
    if not access_token:
        raise Exception("Access token not found in response.")

    log.success("Access token acquired from API")
    return access_token

# --- Web Scraping Functions (Profiles, Posts, Comments, etc.) ---
def parse_profile(response: Response):
    """Parse profile data from hidden scripts on the HTML."""
    assert response.status_code == 200, "Request is blocked, use alternative approaches."
    selector = Selector(response.text)
    data = selector.xpath("//script[@id='__UNIVERSAL_DATA_FOR_REHYDRATION__']/text()").get()
    profile_data = json.loads(data)["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]  
    return profile_data

async def scrape_profiles(urls: List[str]) -> List[Dict]:
    """Scrape TikTok profiles data from their URLs."""
    to_scrape = [client.get(url) for url in urls]
    data = []
    for response in asyncio.as_completed(to_scrape):
        response = await response
        profile_data = parse_profile(response)
        data.append(profile_data)
    log.success(f"Scraped {len(data)} profiles from profile pages")
    return data

def parse_post(response: Response) -> Dict:
    """Parse hidden post data from HTML."""
    assert response.status_code == 200, "Request is blocked, use alternative approaches."
    selector = Selector(response.text)
    data = selector.xpath("//script[@id='__UNIVERSAL_DATA_FOR_REHYDRATION__']/text()").get()
    post_data = json.loads(data)["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]
    parsed_post_data = jmespath.search(
        """{
            id: id,
            desc: desc,
            createTime: createTime,
            video: video.{duration: duration, ratio: ratio, cover: cover, playAddr: playAddr, downloadAddr: downloadAddr, bitrate: bitrate},
            author: author.{id: id, uniqueId: uniqueId, nickname: nickname, avatarLarger: avatarLarger, signature: signature, verified: verified},
            stats: stats,
            locationCreated: locationCreated,
            diversificationLabels: diversificationLabels,
            suggestedWords: suggestedWords,
            contents: contents[].{textExtra: textExtra[].{hashtagName: hashtagName}}
        }""",
        post_data
    )
    return parsed_post_data

async def scrape_posts(urls: List[str]) -> List[Dict]:
    """Scrape TikTok posts data from their URLs."""
    to_scrape = [client.get(url) for url in urls]
    data = []
    for response in asyncio.as_completed(to_scrape):
        response = await response
        post_data = parse_post(response)
        data.append(post_data)
    log.success(f"Scraped {len(data)} posts from post pages")
    return data

async def get_with_retry(url: str, retries: int = MAX_RETRIES) -> Response:
    """Make GET request with retry logic."""
    for attempt in range(retries):
        try:
            response = await client.get(url)
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                log.warning(f"Request blocked (403) on attempt {attempt + 1}/{retries}")
            else:
                log.warning(f"Request failed with status {response.status_code} on attempt {attempt + 1}/{retries}")
        except Exception as e:
            log.error(f"Request error on attempt {attempt + 1}/{retries}: {str(e)}")
        
        if attempt < retries - 1:
            await asyncio.sleep(RETRY_DELAY * (attempt + 1))
    
    raise Exception(f"Failed to get response after {retries} attempts")

def parse_comments(response: Response) -> Dict:
    """Parse comments data from the API response with better error handling."""
    try:
        data = json.loads(response.text)
        if data.get("status_code") != 0:
            error_msg = data.get("status_msg", "Unknown error")
            log.error(f"TikTok API error: {error_msg}")
            return {"comments": [], "total_comments": 0}
        
        comments_data = data.get("comments", [])
        total_comments = data.get("total", 0)
        
        parsed_comments = []
        for comment in comments_data:
            try:
                result = jmespath.search(
                    """{
                        text: text,
                        comment_language: comment_language,
                        digg_count: digg_count,
                        reply_comment_total: reply_comment_total,
                        author_pin: author_pin,
                        create_time: create_time,
                        cid: cid,
                        nickname: user.nickname,
                        unique_id: user.unique_id,
                        aweme_id: aweme_id
                    }""",
                    comment
                )
                if result:
                    parsed_comments.append(result)
            except Exception as e:
                log.warning(f"Error parsing comment: {str(e)}")
                continue
                
        return {"comments": parsed_comments, "total_comments": total_comments}
    except json.JSONDecodeError:
        log.error("Failed to parse JSON response")
        return {"comments": [], "total_comments": 0}
    except Exception as e:
        log.error(f"Error parsing comments: {str(e)}")
        return {"comments": [], "total_comments": 0}

async def scrape_comments(post_id: int, comments_count: int = 20, max_comments: int = None) -> List[Dict]:
    """Scrape comments from TikTok posts with improved error handling."""
    def form_api_url(cursor: int):
        """Form the comments API URL with required parameters."""
        params = {
            "aweme_id": post_id,
            "count": comments_count,
            "cursor": cursor,
            "device_type": "web_pc",
            "version_code": "1.0.0",
            "verifyFp": "verify_m2i59dhw_wdGMHAMU_2hy2_4Zuv_BSSs_PSPvK8Lhu0i6",  # You may update these values as needed.
            "msToken": "ZAEyrf7mLpYaqfHi0AHJ-lt5K1E0Mas3vgsB9i6oBPL-ipzuEvETWIi3-YJdPAyljMJfWVRbzO8w7KO9yJF-yzugQvoly79oojlDzH650qsXXhZW-0A_uMSLhwwCeq30vwS93UnL8vho8E4=",
            "aid": "1988",
            "_signature": "_02B4Z6wo00001GZoSjgAAIDDFm97cV.a-dBmaE6AAH6U0d"
        }
        return f"{TIKTOK_API_BASE}/comment/list/?{urlencode(params)}"
    
    try:
        log.info("Scraping the first comments batch")
        first_page = await get_with_retry(form_api_url(0))
        data = parse_comments(first_page)
        comments_data = data["comments"]
        total_comments = data["total_comments"]

        if not comments_data:
            log.warning("No comments found in the first batch")
            return []

        if max_comments and max_comments < total_comments:
            total_comments = max_comments

        log.info(f"Scraping comments pagination, remaining {total_comments // comments_count - 1} more pages")
        
        tasks = []
        for cursor in range(comments_count, total_comments + comments_count, comments_count):
            tasks.append(get_with_retry(form_api_url(cursor)))

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for response in responses:
            if isinstance(response, Exception):
                log.error(f"Error fetching comments page: {str(response)}")
                continue
            data = parse_comments(response)["comments"]
            comments_data.extend(data)

        log.success(f"Scraped {len(comments_data)} comments from post {post_id}")
        return comments_data
    except Exception as e:
        log.error(f"Error scraping comments: {str(e)}")
        return []

async def download_media(url: str, filename: str):
    """Download media from a given URL."""
    print(url)
    async with client.stream('GET', url) as response:
        if response.status_code == 200:
            async with aiofiles.open(filename, mode='wb') as f:
                async for chunk in response.aiter_bytes():
                    await f.write(chunk)
            log.success(f"Downloaded {filename}")
        else:
            log.error(f"Failed to download {filename}")

def detect_bot(user_data: dict) -> bool:
    """Detect if a user appears to be a bot."""
    if not user_data:
        return False
    bot_indicators = 0
    if user_data.get("followerCount", 0) < 10 and user_data.get("followingCount", 0) > 1000:
        bot_indicators += 1
    if user_data.get("videoCount", 0) > 10000 and user_data.get("followerCount", 0) < 100:
        bot_indicators += 1
    if user_data.get("uniqueId", "").replace("@", "").isdigit() or len(user_data.get("uniqueId", "")) > 16:
        bot_indicators += 1
    if "bot" in user_data.get("signature", "").lower():
        bot_indicators += 1
    if "default" in user_data.get("avatarLarger", "").lower():
        bot_indicators += 1
    return bot_indicators >= 2

async def process_profile(profile_data: Dict, base_dir: str, depth: int = 0, max_depth: int = 2):
    user_id = profile_data['user'].get('id', 'unknown_id')
    user_stats = profile_data['stats']
    user_dir = os.path.join(base_dir, user_id)
    os.makedirs(user_dir, exist_ok=True)

    # Download profile picture
    profile_pic_url = profile_data['user'].get('avatarLarger', '')
    if profile_pic_url:
        profile_pic_path = os.path.join(user_dir, f"{user_id}_profile_pic.jpg")
        await download_media(profile_pic_url, profile_pic_path)

    # Prepare profile data JSON structure
    profile_json = {
        "platform": "TikTok",
        "userID": user_id,
        "screen_name": profile_data['user'].get('nickname', ''),
        "name": profile_data['user'].get('nickname', ''),
        "nickname": profile_data['user'].get('nickname', ''),
        "unique_id": profile_data['user'].get('uniqueId', ''),
        "followers": f"{user_stats.get('followerCount', 0):,}",
        "profile_image": profile_pic_url,
        "profile_image_url": profile_pic_url,
        "avatarLarger": profile_data['user'].get('avatarLarger', ''),
        "avatarMedium": profile_data['user'].get('avatarMedium', ''),
        "avatarThumb": profile_data['user'].get('avatarThumb', ''),
        "bio": profile_data['user'].get('signature', ''),
        "description": profile_data['user'].get('signature', ''),
        "bio_links": profile_data['user'].get('bioLink', {}).get('link', '').split(),
        "homepage": f"https://www.tiktok.com/@{profile_data['user'].get('uniqueId', '')}",
        "category": "",
        "business_category": "",
        "friends_count": f"{user_stats.get('followingCount', 0):,}",
        "statuses_count": "",
        "video_count": f"{user_stats.get('videoCount', 0):,}",
        "image_count": "",
        "phone": "",
        "email": "",
        "is_private": profile_data['user'].get('privateAccount', False),
        "is_verified": profile_data['user'].get('verified', False),
        "location": {
            "city_name": "",
            "city_id": "",
            "latitude": "",
            "longitude": "",
            "street_address": "",
            "zip_code": "",
            "region": profile_data['user'].get('region', '')
        },
        "tiktok_id": user_id,
        "duetSetting": str(profile_data['user'].get('duetSetting', 0)),
        "stitchSetting": str(profile_data['user'].get('stitchSetting', 0)),
        "privateAccount": profile_data['user'].get('privateAccount', False),
        "createTime": datetime.fromtimestamp(profile_data['user'].get('createTime', 0)).isoformat(),
        "signature": profile_data['user'].get('signature', ''),
        "eventList": [],
        "video_list": [],
        "is_organization": False,
        "profile_tab": {
            "showMusicTab": True,
            "showQuestionTab": False,
            "showPlayListTab": True
        },
        "current_timestamp": datetime.now().isoformat(),
        "following_user_ids": [],
        "followers_user_ids": [],
        "is_bot": detect_bot(profile_data['user'])
    }
    if depth < max_depth:
        # Fetch followers and following (limit example: 100 each)
        connections = await scrape_followers_following(user_id, max_count=100)
        profile_json["followers_user_ids"] = connections["followers"]
        profile_json["following_user_ids"] = connections["following"]

        # Scrape posts (limit to 50)
        posts = await scrape_posts(
            [f"https://www.tiktok.com/@{profile_data['user'].get('uniqueId')}/video/{post_id}"
             for post_id in profile_data.get('items', [])[:50]]
        )
        for post in posts:
            comments = await scrape_comments(post["id"], max_comments=100)
            await process_post(post, comments, user_dir)
            # Process commenters' profiles (if desired)
            for comment in comments:
                commenter_profile = await scrape_profiles([f"https://www.tiktok.com/@{comment['unique_id']}"])
                if commenter_profile:
                    await process_profile(commenter_profile[0], base_dir, depth + 1, max_depth)

    # Save profile data
    profile_data_path = os.path.join(user_dir, f"{user_id}.json")
    with open(profile_data_path, 'w', encoding='utf-8') as f:
        json.dump(profile_json, f, indent=2, ensure_ascii=False)
    log.info(f"Processed profile: {user_id} at depth {depth}")

async def scrape_followers_following(user_id: str, max_count: int = 100) -> Dict[str, List[str]]:
    async def fetch_connections(connection_type: str, cursor: int = 0) -> Dict:
        params = {
            "user_id": user_id,
            "count": 20,
            "max_time": 0,
            "min_time": 0,
            "source_type": 1,
            "cursor": cursor,
            "sec_user_id": "",
            "address_book_access": 1,
            "gps_access": 0,
            "from": 0,
            "verifyFp": "verify_m2i59dhw_wdGMHAMU_2hy2_4Zuv_BSSs_PSPvK8Lhu0i6",
            "msToken": "ZAEyrf7mLpYaqfHi0AHJ-lt5K1E0Mas3vgsB9i6oBPL-ipzuEvETWIi3-YJdPAyljMJfWVRbzO8w7KO9yJF-yzugQvoly79oojlDzH650qsXXhZW-0A_uMSLhwwCeq30vwS93UnL8vho8E4=",
        }
        url = f"{TIKTOK_API_BASE}/user/{connection_type}/list/?{urlencode(params)}"
        response = await get_with_retry(url)
        return json.loads(response.text)

    async def fetch_all_connections(connection_type: str) -> List[str]:
        connections = []
        cursor = 0
        while len(connections) < max_count:
            data = await fetch_connections(connection_type, cursor)
            if not data.get("user_list"):
                break
            connections.extend([user["user_info"]["uid"] for user in data["user_list"]])
            if not data.get("has_more"):
                break
            cursor = data.get("cursor", 0)
        return connections[:max_count]

    followers = await fetch_all_connections("follower")
    following = await fetch_all_connections("following")
    return {"followers": followers, "following": following}

async def process_post(post_data: Dict, comment_data: List[Dict], base_dir: str):
    user_id = post_data['author']['id']
    user_name = post_data['author']['uniqueId'] 
    profile_pic_url = post_data['author']['avatarLarger']
    post_id = post_data['id']
    post_dir = os.path.join(base_dir, user_id, post_id)
    os.makedirs(post_dir, exist_ok=True)
    # Download post media (video)
    video_url = post_data['video']['downloadAddr']
    video_path = os.path.join(post_dir, f"{post_id}_video.mp4")
    await download_media(video_url, video_path)

    processed_comments = []
    for comment in comment_data:
        processed_comment = {
            "userName": comment.get('nickname', ''),
            "text": comment.get('text', ''),
            "time": (datetime.fromtimestamp(comment.get('create_time')).isoformat()
                     if isinstance(comment.get('create_time'), (int, float)) else ""),
            "reaction_count": comment.get('digg_count', '0')
        }
        processed_comments.append(processed_comment)

    post_json = {
        "platform": "TikTok",
        "current_timestamp": datetime.now().isoformat(),
        "userID": user_id,
        "userName": user_name,
        "profile_pic_url": profile_pic_url,
        "is_verified": post_data['author']['verified'],
        "dataOfPost": post_data['desc'],
        "post_image_url": post_data['video']['cover'],
        "likes_number": str(post_data['stats']['diggCount']),
        "shares_number": str(post_data['stats']['shareCount']),
        "comments_number": str(post_data['stats']['commentCount']),
        "post_date": datetime.fromtimestamp(int(post_data['createTime'])).isoformat(),
        "post_id": post_id,
        "listOfComments": processed_comments,
        "listOfLikes": [],
        "listOfShares": [],
        "shortcode": "",
        "dimensions": "",
        "src": "",
        "src_attached": "",
        "has_audio": "",
        "video_url": video_url,
        "views": str(post_data['stats']['playCount']),
        "type": "video",
        "video_duration": post_data['video']['duration'],
        "is_video": True,
        "captions": post_data['desc'],
        "comments_disabled": "",
        "locationCreated": post_data['locationCreated'],
        "diversificationLabels": post_data.get('diversificationLabels', []),
        "contents": post_data.get('contents', []),
        "attached_urls": [],
        "attached_media": [],
        "tagged_users": [],
        "tagged_hashtags": [],
        "bookmark_count": [],
        "quote_count": [],
        "reply_count": [],
        "retweet_count": [],
        "is_quote": "",
        "is_retweet": "",
        "language": "",
        "conversation_id": [],
        "source": "",
        "poll": []
    }
    post_data_path = os.path.join(post_dir, f"{post_id}.json")
    with open(post_data_path, 'w', encoding='utf-8') as f:
        json.dump(post_json, f, indent=2, ensure_ascii=False)
    log.info(f"Processed post: {post_id}")

# --- Main Runner Functions ---
async def main(initial_profiles: List[str], base_dir: str, max_depth: int):
    # Integrate the API: fetch the access token and add it to the client's headers.
    try:
        access_token = await get_client_access_token(CLIENT_KEY, CLIENT_SECRET)
        client.headers["Authorization"] = f"Bearer {access_token}"
    except Exception as e:
        log.error(f"Error fetching access token: {e}")
        return

    for profile_url in initial_profiles:
        profile_data = await scrape_profiles([profile_url])
        if profile_data:
            await process_profile(profile_data[0], base_dir, 0, max_depth)

if __name__ == "__main__":
    initial_profiles = [
        "https://www.tiktok.com/@jaycapalotx2",
        "https://www.tiktok.com/@zake1231484"
    ]
    base_dir = r"D:\Research emergency\tiktok\scraped_data"
    max_depth = 2
    asyncio.run(main(initial_profiles, base_dir, max_depth))
