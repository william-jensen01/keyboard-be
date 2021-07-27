from bs4 import BeautifulSoup
import requests

# get the last page of a forum
def get_last_page(url):
  numbers = []
  req = requests.get(url)
  soup = BeautifulSoup(req.content, 'html.parser')
  pages = soup.find('div', class_="pagelinks floatleft")
  temp = pages.find_all('a')

  for a in temp:
    numbers.append(a.text)

  last_page = numbers[-3]

  return last_page

# get all the data on the forum page for each post (data that is exclusive to that page)
def get_page_posts_small_data(url):
  req = requests.get(url)
  soup = BeautifulSoup(req.content, 'html.parser')

  all_posts = soup.find_all('td', class_='subject windowbg2')
  all_posts_activity_stats = soup.find_all('td', class_='stats windowbg')
  all_last_updated_stats = soup.find_all('td', class_='lastpost windowbg2')

  all_posts_url = []
  all_topic_ids = []
  all_activity_stats = []
  all_last_updated = []

  for post in all_posts:
    weird_url = post.find('a').get('href')
    url_list = weird_url.split('=')
    topic = url_list[-1]
    topic_id = topic.split('.')[0]
    post_url = f'https://geekhack.org/index.php?topic={topic_id}.0'
    all_posts_url.append(post_url)
    all_topic_ids.append(topic_id)

  for post_activity in all_posts_activity_stats:
    all_activity_stats.append(post_activity.text.split())
  
  for post_last_updated in all_last_updated_stats:
    last_updated_reference_list = post_last_updated.text.split()
    time = last_updated_reference_list[4]
    day_of_week = last_updated_reference_list[0][:-1]
    day = last_updated_reference_list[1]
    month = last_updated_reference_list[2]
    year = last_updated_reference_list[3][:-1]
    last_updated = f"{time} {day_of_week}, {month} {day}, {year}" # example = "Wed, March 31, 2021"
    all_last_updated.append(last_updated)

  small_data = []

  for i in range(len(all_posts_url)):
    post_small_data = {
      'url': all_posts_url[i],
      'stats': all_activity_stats[i],
      'last_updated': all_last_updated[i],
      'topic': all_topic_ids[i]
    }
    small_data.append(post_small_data)
  return small_data

def get_all_post_data(small_data, post_type):
  url = small_data['url']
  replies = small_data['stats'][0]
  views = small_data['stats'][2]
  last_updated = small_data['last_updated']
  topic_id = small_data['topic']

  req = requests.get(url)
  soup = BeautifulSoup(req.content, 'html.parser')

  post_container = soup.find('div', class_="post")
  poster_container = soup.find('div', class_="poster")

  post_title = soup.find('h5').text.replace(f"\n", '').lstrip()

  post_creator = poster_container.find('a').text

  date_created_reference = soup.find('div', class_="smalltext").text[7:-12]
  day_of_week = date_created_reference[0:5]
  day = date_created_reference[5:7]
  month = date_created_reference[8:-5]
  year = date_created_reference[-4:]
  date_created = f"{day_of_week}, {month} {day}, {year}"
  # example: "Wed, March 31, 2021"

  post_images = []
  images = post_container.find_all('img')
  for image in images:
      image_url = image.get('src')
      post_images.append(image_url)

  all_data = {
  'title': post_title,
  'topic_id': topic_id,
  'url': url,
  'creator': post_creator,
  'created': date_created,
  'images': post_images,
  'views': views,
  'replies': replies,
  'last_updated': last_updated,
  'post_type': post_type
  }
  return all_data

def go_through_all_posts(url, num_pages, small_post_data, post_type, post_model, image_model, db):
  count = 0
  for i in range(1, num_pages + 1):
    print(f"starting scraping - {post_type}")
    print(f"{i} of {num_pages}")
    current_url = f"{url}{count}"
    current_page_small_data = small_post_data[i-1]
    for post_data in current_page_small_data:
      get_all_post_data(post_data, post_type, post_model, image_model, db)
    count += 50
  print(f"finished scraping {i} of {num_pages} - {post_type}")

# update post by id
# paramets include serialized post object, and request data
# Note: all fields are required
def update_post(post, data):
  post.title = data['title']
  post.topic_id = data['topic_id']
  post.url = data['url']
  post.creator = data['creator']
  post.created = data['created']
  post.views = data['views']
  post.replies = data['replies']
  post.last_updated = data['last_updated']
  post.post_type = data['post_type']
  return post

def check_post(post_all_data, post_model, image_model, db):
  post_topic_id = int(post_all_data['topic_id'])
  post_time = post_all_data['last_updated']

  db_post = post_model.query.filter_by(topic_id=post_topic_id).first()
  if db_post:
    print('post exists ... updating')
    db_post_time = db_post.last_updated
    if db_post_time == post_time and db_post.topic_id == post_topic_id:
      return 1
    else:
      updated_db_post = update_post(db_post, post_all_data)
      db.session.commit()
      if len(db_post.images) != len(post_all_data['images']):
        print('adding new images')
        for img_url in post_all_data['images']:
          image = image_model.query.filter_by(image_url=img_url).first()
          if image:
            continue
          else:
            new_db_image = image_model(img_url, updated_db_post)
            db.session.add(new_db_image)
            db.session.commit()
      return 0

    db.session.close()
  else:
    print("post doesn't exist, adding it to db")
    new_db_post = post_model(post_all_data['title'], post_all_data['topic_id'], post_all_data['url'], post_all_data['creator'], post_all_data['created'], post_all_data['views'], post_all_data['replies'], post_all_data['last_updated'], post_all_data['post_type'])
    db.session.add(new_db_post)
    db.session.commit()

    for img_url in post_all_data['images']:
      new_db_image = image_model(img_url, new_db_post)
      db.session.add(new_db_image)
      db.session.commit()
    db.session.close()
    return 0

def update_db_by_type(post_type, post_model, image_model, db):
  post_type = post_type.upper()
  url = ''

  if post_type == 'IC':
    url = 'https://geekhack.org/index.php?board=132.0'
    page_small_data = get_page_posts_small_data(url)
    for post_small_data in page_small_data:
      post_all_data = get_all_post_data(post_small_data, post_type)
      check_post(post_all_data, post_model, image_model, db)

  if post_type == 'GB':
    url = 'https://geekhack.org/index.php?board=70.0'
    page_small_data = get_page_posts_small_data(url)
    for post_small_data in page_small_data:
      post_all_data = get_all_post_data(post_small_data, post_type)
      check_post(post_all_data, post_model, image_model, db)

  if post_type == 'DB':
    update_db_by_type('IC', post_model, image_model, db)
    update_db_by_type('GB', post_model, image_model, db)
      
def populate_db(url, num_pages, post_type, post_model, image_model, db):
  count = 0
  for i in range(1, int(num_pages) + 1):
    print(f"starting scraping - {post_type}")
    print(f"{i} of {num_pages}")
    current_url = f"{url}{count}"
    small_page_data = get_page_posts_small_data(current_url)
    for post_small_data in small_page_data:
      post_all_data = get_all_post_data(post_small_data, post_type)
      check_post(post_all_data, post_model, image_model, db)
    count += 50
    print(f"finished scraping {i} of {num_pages} - {post_type}")