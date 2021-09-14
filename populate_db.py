import requests
import os

from functions import get_last_page, get_page_posts_small_data, get_all_post_data

def populate_helper(post_type, last_page, url):
    API_URL = os.getenv('API_URL')
    count = 0
    for i in range(1, int(last_page) + 1):
        print(f"starting scraping {i} of {last_page} - {post_type}")
        current_url = f"{url}{count}"
        small_page_data = get_page_posts_small_data(current_url)
        for post_small_data in small_page_data:
            post_all_data = get_all_post_data(post_small_data)
            print(f"adding {post_all_data['title']}")
            requests.post(f"{API_URL}/{post_type}", json = post_all_data)
        count += 50
        print(f"finished scraping {i} of {last_page} - {post_type}")

def populate():
    IC_url = 'https://geekhack.org/index.php?board=132.'
    GB_url = 'https://geekhack.org/index.php?board=70.'    
    last_page_IC = get_last_page(IC_url)
    last_page_GB = get_last_page(GB_url)

    populate_helper('IC', last_page_IC, IC_url)
    populate_helper('GB', last_page_GB, GB_url)

populate()