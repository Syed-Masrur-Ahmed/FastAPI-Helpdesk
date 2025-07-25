import cloudscraper
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import requests 
import certifi
from urllib.parse import urljoin

def scrape_bluehost_help_center():
    """
    Scrapes articles from the Bluehost Help Center by first finding all categories,
    then scraping all articles within each category.
    """
    base_url = "https://www.bluehost.com"
    main_help_url = urljoin(base_url, "/help")
    
    scraper = cloudscraper.create_scraper()
    
    print(f"--- Starting Bluehost Scraper ---")
    print(f"Fetching categories from: {main_help_url}")

    # --- 1. Get the main help page to find all category links ---
    try:
        main_page = scraper.get(main_help_url, timeout=30, verify=certifi.where())
        main_page.raise_for_status()
    except Exception as e:
        print(f"❌ Error fetching the main help page: {e}")
        return

    main_soup = BeautifulSoup(main_page.content, "html.parser")
    
    # --- 2. Find all category links ---
    # Based on inspection, category links are within a div with class 'wh-categories'
    category_container = main_soup.find("div", class_="wh-categories")
    if not category_container:
        print("❌ Could not find category container. Bluehost's website structure may have changed.")
        return
        
    category_links = [urljoin(base_url, a['href']) for a in category_container.find_all("a", href=True)]

    if not category_links:
        print("❌ Could not find any category links.")
        return

    print(f"Found {len(category_links)} categories to process.")

    # --- API Configuration ---
    api_url = "http://127.0.0.1:8000/items/"
    api_post_headers = {"Content-Type": "application/json"}
    bluehost_category_id = 3 # Using a new category ID for Bluehost articles

    # --- 3. Loop through each category to get article links ---
    for category_url in category_links:
        print(f"\nProcessing Category: {category_url}")
        try:
            category_page = scraper.get(category_url, timeout=30, verify=certifi.where())
            category_page.raise_for_status()
            category_soup = BeautifulSoup(category_page.content, "html.parser")

            # --- Find all article links within this category ---
            # Articles are in a div with class 'wh-articles-list'
            article_list_div = category_soup.find("div", class_="wh-articles-list")
            if not article_list_div:
                print(f"  -> No article list found in this category. Skipping.")
                continue

            articles_to_scrape = [urljoin(base_url, a['href']) for a in article_list_div.find_all("a", href=True)]
            print(f"  -> Found {len(articles_to_scrape)} articles in this category.")

            # --- 4. Loop through each article and scrape its content ---
            for article_url in articles_to_scrape:
                try:
                    article_page = scraper.get(article_url, timeout=20, verify=certifi.where())
                    article_page.raise_for_status()
                    article_soup = BeautifulSoup(article_page.content, "html.parser")

                    # Extract title and content
                    title_element = article_soup.find("h1", class_="wh-article-title")
                    content_element = article_soup.find("div", class_="wh-article-content")

                    if not title_element or not content_element:
                        print(f"    - ⚠️ Could not find title/content for {article_url}. Skipping.")
                        continue
                    
                    article_title = title_element.get_text(strip=True)
                    answer_text = content_element.get_text(strip=True, separator='\n')

                    # --- Prepare data and POST to your API ---
                    item_data = {
                        "title": article_title,
                        "question": article_title,
                        "answer": answer_text,
                        "votes": 0, "recommendations": 0,
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                        "category_id": bluehost_category_id,
                        "enabled": True, "team_id": None, "order": None
                    }

                    response = requests.post(api_url, data=json.dumps(item_data), headers=api_post_headers)

                    if response.status_code == 200:
                        print(f"    - ✅ Successfully added '{article_title}'")
                    else:
                        print(f"    - ❌ Failed to add '{article_title}' (Status: {response.status_code})")

                except requests.exceptions.ConnectionError:
                    print("❌ Connection Error: Could not connect to the API. Halting script.")
                    return
                except Exception as e:
                    print(f"    - ❌ Error processing article {article_url}: {e}")

        except Exception as e:
            print(f"  -> ❌ Error processing category {category_url}: {e}")


if __name__ == "__main__":
    # You will need to install the required libraries:
    # pip install cloudscraper beautifulsoup4 requests certifi
    scrape_bluehost_help_center()
