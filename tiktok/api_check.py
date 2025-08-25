import asyncio
import httpx

CLIENT_KEY = "awzbf3ywv65u253d"
CLIENT_SECRET = "ZKXBkCpHtTG7sDBUhy0fIrqXmHZqMNC5"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

async def get_client_access_token():
    data = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(TOKEN_URL, data=data, headers=headers)
        if response.status_code == 200:
            token_data = response.json()
            print("Access Token:", token_data.get("access_token"))
            print("Expires In:", token_data.get("expires_in"), "seconds")
            print("Token Type:", token_data.get("token_type"))
        else:
            print("Error:", response.status_code, response.text)

if __name__ == "__main__":
    asyncio.run(get_client_access_token())
