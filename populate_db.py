from app import Post, Image, db
from functions import get_last_page, get_page_posts_small_data, get_all_post_data

def populate_helper(post_type, last_page, url):
    count = 0
    for i in range(1, int(last_page) + 1):
        print(f"starting scraping - {post_type}")
        print(f"{i} of {last_page}")
        current_url = f"{url}{count}"
        small_page_data = get_page_posts_small_data(current_url)
        for post_small_data in small_page_data:
            print('adding new post')
            post_all_data = get_all_post_data(post_small_data, post_type)
            new_db_post = Post(post_all_data['title'], post_all_data['topic_id'], post_all_data['url'], post_all_data['creator'], post_all_data['created'], post_all_data['views'], post_all_data['replies'], post_all_data['last_updated'], post_all_data['post_type'])
            db.session.add(new_db_post)
            db.session.commit()

            for img_url in post_all_data['images']:
                new_db_image = Image(img_url, new_db_post)
                db.session.add(new_db_image)
                db.session.commit()
            db.session.close()
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