import cloudscraper
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import re
import requests # Import at the top
import certifi # Import certifi to provide SSL certificates
from urllib.parse import urljoin

def scrape_and_add_faqs():
    """
    Scrapes web hosting articles from the GoDaddy Help Center and adds them to the database via the API.
    Uses cloudscraper to bypass anti-bot measures.
    """
    # --- Target URL for scraping: GoDaddy's cPanel Hosting Help section ---
    base_url = "https://www.godaddy.com"
    # The URL now includes a region code, which can help with access.
    scrape_url = urljoin(base_url, "/en-in/help/web-hosting-cpanel-1000006")
    
    # --- Create a cloudscraper instance configured to mimic a real browser ---
    # This helps bypass more advanced anti-bot measures that cause 403 errors.
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'mobile': False
        }
    )
    
    print(f"Attempting to scrape article links from: {scrape_url}")

    try:
        # --- Fetch the HTML content of the main help page ---
        page = scraper.get(scrape_url, timeout=20, verify=certifi.where())
        page.raise_for_status()
    except Exception as e:
        print(f"❌ Error fetching the main help page URL: {e}")
        return

    # --- Parse the HTML to find article links ---
    soup = BeautifulSoup(page.content, "html.parser")
    
    # --- GoDaddy Selector: Find all links within the main article list ---
    # The links are inside a div with the class 'article-list-container'
    article_list_container = soup.find("div", class_="article-list-container")
    if not article_list_container:
        print("❌ Could not find the article list container. GoDaddy's website structure may have changed.")
        return
        
    article_links = article_list_container.find_all("a")

    if not article_links:
        print("❌ Could not find any article links on the page.")
        return

    print(f"Found {len(article_links)} articles to process.")

    # --- API Configuration ---
    api_url = "http://127.0.0.1:8000/items/"
    api_post_headers = {"Content-Type": "application/json"}
    web_hosting_category_id = 2 # Using a new category ID for GoDaddy articles

    for link in article_links:
        article_title = link.get_text(strip=True)
        article_href = link.get('href')

        if not article_title or not article_href:
            continue

        # --- Construct the full URL for the article page ---
        article_url = urljoin(base_url, article_href)
        print(f"\nScraping article: '{article_title}'")
        print(f"  -> from {article_url}")

        try:
            # --- Scrape the individual article page ---
            article_page = scraper.get(article_url, timeout=20, verify=certifi.where())
            article_page.raise_for_status()
            article_soup = BeautifulSoup(article_page.content, "html.parser")

            # --- Extract the main content of the article ---
            # The content is within a div with the class 'article-body'
            content_element = article_soup.find("div", class_="article-body")
            if not content_element:
                print(f"   ⚠️ Could not find content for '{article_title}'. Skipping.")
                continue
            
            # Get all text from the article body, separating paragraphs with newlines
            answer_text = content_element.get_text(strip=True, separator='\n')

            # --- Prepare the data payload for the API ---
            item_data = {
                "title": article_title,
                "question": article_title, # Using the article title as the "question"
                "answer": answer_text,
                "votes": 0,
                "recommendations": 0,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "category_id": web_hosting_category_id,
                "enabled": True,
                "team_id": None,
                "order": None
            }

            # --- Send the POST request to the API ---
            response = requests.post(api_url, data=json.dumps(item_data), headers=api_post_headers)

            if response.status_code == 200:
                print(f"   ✅ Successfully added to database.")
            else:
                print(f"   ❌ Failed to add to database.")
                print(f"      Status Code: {response.status_code}")
                print(f"      Response: {response.text}")

        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Could not connect to the API. Halting script.")
            print("   Please ensure the FastAPI server is running.")
            return
        except Exception as e:
            print(f"   ❌ An unexpected error occurred while processing this article: {e}")


if __name__ == "__main__":
    # You will need to install the required libraries:
    # pip install cloudscraper beautifulsoup4 requests certifi
    scrape_and_add_faqs()

