import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Directory to save downloaded files
save_dir = "downloaded_files"
os.makedirs(save_dir, exist_ok=True)

# Function to fetch websites dynamically using a search engine (Google or Bing)
def search_websites(query, max_sites=10):
    print("Searching for websites...")
    search_url = f"https://www.google.com/search?q={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(search_url, headers=headers, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract URLs from the search results
    website_links = []
    for link in soup.find_all("a"):
        href = link.get("href")
        if href and "http" in href:
            url = href.split("&")[0].replace("/url?q=", "")
            if url not in website_links:
                website_links.append(url)
        if len(website_links) >= max_sites:
            break

    print(f"Found {len(website_links)} websites.")
    return website_links

# Function to download a file
def download_file(url, save_path):
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()  # Check for request errors
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded: {save_path}")
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False

# Function to process a website and download files
def process_website(base_url):
    print(f"Processing website: {base_url}")
    try:
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Find all file links (only .pdf and .txt files)
        file_links = soup.find_all("a", href=lambda href: href and (href.endswith(".pdf") or href.endswith(".txt")))

        if not file_links:
            print(f"No files found on {base_url}.")
            return 0

        downloaded_files = set()
        count = 0

        for link in file_links:
            file_url = link["href"]
            if not file_url.startswith("http"):
                file_url = urljoin(base_url, file_url)  # Construct full URL if relative
            if file_url in downloaded_files:
                continue  # Skip duplicate files
            downloaded_files.add(file_url)

            file_name = os.path.join(save_dir, f"{base_url.replace('https://', '').replace('/', '_')}_{len(downloaded_files)}{os.path.splitext(file_url)[-1]}")
            if download_file(file_url, file_name):
                count += 1
                if count >= 100:  # Stop after 100 files
                    break

        print(f"Downloaded {count} files from {base_url}.")
        return count

    except Exception as e:
        print(f"Error processing {base_url}: {e}")
        return 0

# Main function to manage the search and download process
def main():
    query = "USA election survey filetype:pdf OR filetype:txt"
    total_downloaded = 0
    processed_sites = set()

    while total_downloaded < 100:
        websites = search_websites(query, max_sites=10)

        for website in websites:
            if website in processed_sites:
                continue

            downloaded = process_website(website)
            processed_sites.add(website)
            total_downloaded += downloaded

            if total_downloaded >= 100:
                break

        if not websites:
            print("No more websites found. Stopping.")
            break

    print(f"Total files downloaded: {total_downloaded}")

if __name__ == "__main__":
    main()
