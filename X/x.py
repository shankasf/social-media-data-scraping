import requests
import json
import time

def fetch_tweets_all_options(bearer_token, query, max_results=100, request_limit=5):
    """
    Fetch tweets using the GET /2/tweets/search/recent endpoint with all available parameters.
    Includes rate limit handling: if a 429 is received, the code waits until the rate limit resets.
    
    Parameters include:
      - Query filters (query, start_time, end_time, etc.)
      - Tweet Fields
      - Expansions
      - Media, Poll, User, and Place Fields

    Args:
        bearer_token (str): Your API Bearer Token.
        query (str): The search query string.
        max_results (int): Number of tweets per request (between 10 and 100).
        request_limit (int): Maximum number of requests (pagination limit).

    Returns:
        dict: Combined result containing tweet data and expanded objects.
    """
    url = "https://api.x.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    
    params = {
        # Required search query.
        "query": query,
        # Optional time filters (ISO 8601 format, adjust as needed)
        # "start_time": "2023-02-10T00:00:00Z",
        # "end_time":   "2023-02-17T00:00:00Z",
        # Optional tweet ID filters.
        # "since_id": "0",
        # "until_id": "",
        # Number of tweets per request.
        "max_results": max_results,
        # Sorting order: "recency" or "relevancy"
        "sort_order": "recency",
        # Additional Tweet Fields:
        "tweet.fields": (
            "id,text,author_id,created_at,public_metrics,lang,conversation_id,"
            "attachments,card_uri,community_id,context_annotations,display_text_range,"
            "edit_controls,edit_history_tweet_ids,entities,geo,in_reply_to_user_id,"
            "media_metadata,non_public_metrics,note_tweet,organic_metrics,possibly_sensitive,"
            "promoted_metrics,referenced_tweets,reply_settings,scopes,source,withheld"
        ),
        # Expansions for related objects:
        "expansions": (
            "article.cover_media,article.media_entities,attachments.media_keys,"
            "attachments.media_source_tweet,attachments.poll_ids,author_id,edit_history_tweet_ids,"
            "entities.mentions.username,geo.place_id,in_reply_to_user_id,"
            "entities.note.mentions.username,referenced_tweets.id,referenced_tweets.id.author_id"
        ),
        # Media Fields:
        "media.fields": (
            "alt_text,duration_ms,height,media_key,non_public_metrics,organic_metrics,"
            "preview_image_url,promoted_metrics,public_metrics,type,url,variants,width"
        ),
        # Poll Fields:
        "poll.fields": "duration_minutes,end_datetime,id,options,voting_status",
        # User Fields:
        "user.fields": (
            "affiliation,connection_status,created_at,description,entities,id,"
            "is_identity_verified,location,most_recent_tweet_id,name,parody,pinned_tweet_id,"
            "profile_banner_url,profile_image_url,protected,public_metrics,receives_your_dm,"
            "subscription,subscription_type,url,username,verified,verified_followers_count,"
            "verified_type,withheld"
        ),
        # Place Fields:
        "place.fields": "contained_within,country,country_code,full_name,geo,id,name,place_type"
    }
    
    combined_result = {"tweets": [], "includes": {}}
    next_token = None
    i = 0

    while i < request_limit:
        if next_token:
            params["next_token"] = next_token
        
        response = requests.get(url, headers=headers, params=params)
        
        # Rate limit handling:
        if response.status_code == 429:
            reset = response.headers.get("x-rate-limit-reset")
            if reset:
                reset_time = int(reset)
                current_time = int(time.time())
                sleep_duration = reset_time - current_time + 5  # 5-second buffer
                if sleep_duration > 0:
                    print(f"Rate limit exceeded. Sleeping for {sleep_duration} seconds.")
                    time.sleep(sleep_duration)
                    continue  # Retry after waiting
            else:
                print("Rate limit exceeded; no reset header found. Sleeping for 60 seconds.")
                time.sleep(60)
                continue

        elif response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            break
        
        data = response.json()
        tweets = data.get("data", [])
        combined_result["tweets"].extend(tweets)
        
        # Merge expanded objects from the "includes" section.
        includes = data.get("includes", {})
        for key, items in includes.items():
            if key in combined_result["includes"]:
                combined_result["includes"][key].extend(items)
            else:
                combined_result["includes"][key] = items
        
        meta = data.get("meta", {})
        next_token = meta.get("next_token")
        if not next_token:
            print("No further pages available.")
            break
        
        i += 1
        time.sleep(1)  # Brief pause between requests
    
    return combined_result

def main():
    # Replace with your actual Bearer Token.
    BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAAVezQEAAAAAXjap0IbfnW3iNXlr6O%2Bp8ECwOgk%3Dv6w2gEcV6Im6jwbZPDnQZv1eQG0n4bMZphm8550iOXOgFjA6wX"
    
    # Define your search query.
    query = "Donald J Trump"
    
    # Fetch tweets with all available parameters and rate limit handling.
    result = fetch_tweets_all_options(BEARER_TOKEN, query)
    
    # Save the result to a JSON file.
    with open("tweets_all_options.json", "w") as f:
        json.dump(result, f, indent=4)
    
    total_tweets = len(result.get("tweets", []))
    print(f"Fetched {total_tweets} tweets with all options. Data saved to 'tweets_all_options.json'.")

if __name__ == "__main__":
    main()
