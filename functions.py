from bs4 import BeautifulSoup
import requests
import re

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

  post_type = ''
  board_num = re.split('\.|\=', url)[-2]
  if board_num == '132':
    post_type = 'IC'
  if board_num == '70':
    post_type = 'GB'

  all_posts = soup.find_all('td', class_='subject')
  all_last_updated_stats = soup.find_all('td', class_='lastpost')

  all_posts_url = []
  all_topic_ids = []
  all_activity_stats = []
  all_last_updated = []

  for post in all_posts:
    weird_url = post.find('a').get('href')
    url_list = weird_url.split('=')
    topic_id = url_list[-1].split('.')[0]
    post_url = f'https://geekhack.org/index.php?topic={topic_id}.0'
    all_posts_url.append(post_url)
    all_topic_ids.append(topic_id)
  
  for post_last_updated in all_last_updated_stats:
    last_updated_reference_list = post_last_updated.text.split()
    time = last_updated_reference_list[4]
    day_of_week = last_updated_reference_list[0][:-1]
    day = last_updated_reference_list[1]
    month = last_updated_reference_list[2]
    year = last_updated_reference_list[3][:-1]
    last_updated = f"{time} {day_of_week}, {month} {day}, {year}" # example: "10:30:17 Wed, March 31, 2021"
    all_last_updated.append(last_updated)

  small_data = []
  unaccepted_topic_ids = set(('36672', '70569', '77272', '57761', '88717', '36773'))
  for i in range(len(all_posts_url)):
    if all_topic_ids[i] not in unaccepted_topic_ids:
      post_small_data = {
        'url': all_posts_url[i],
        'last_updated': all_last_updated[i],
        'topic': all_topic_ids[i],
        'post_type': post_type
      }
      small_data.append(post_small_data)
  return small_data

def get_all_post_data(small_data):
  url = small_data['url']
  last_updated = small_data['last_updated']
  topic_id = small_data['topic']
  post_type = small_data['post_type']

  req = requests.get(url)
  soup = BeautifulSoup(req.content, 'html.parser')

  post_container = soup.find('div', class_="post")
  poster_container = soup.find('div', class_="poster")

  post_title = soup.find('h5').text.replace(f"\n", '').lstrip()

  post_creator = poster_container.find('h4').text.replace(f"\n", '').replace(f"\t", '')

  date_created_reference_list = soup.find('div', class_="smalltext").text.split()
  time = date_created_reference_list[6]
  day_of_week = date_created_reference_list[2][:-1]
  day = date_created_reference_list[3]
  month = date_created_reference_list[4]
  year = date_created_reference_list[5][:-1]
  date_created = f"{time} {day_of_week}, {month} {day}, {year}" # example: "10:30:17 Wed, March 31, 2021"

  post_images = []
  images = post_container.find_all('img')
  for image in images:
    image_url = image.get('src')
    # if url is geekhack, remove PHPSESSID from url
    if image_url.startswith('https://geekhack.org'):
      split_url = re.split('\?|&', image_url) # split the url by ? and &
      new_url = f"{split_url[0]}?{split_url[2]}" # create new url but leave phpsessid part out
      post_images.append(new_url)
    # if url starts with cdn.geekhack, don't add it because it's an emoji
    # there are 2 different urls for geekhack 'images' -- cdn.geekhack (emojis - yes, they count as images) and geekhack (normal images)
    elif image_url.startswith('https://cdn.geekhack.org'):
      pass
    # if url is from discord split and if specific index isn't 'attachments' don't add it
    elif image_url.startswith('https://cdn.discordapp'):
      split_url = image_url.split('/')
      if split_url[3] == 'attachments':
        post_images.append(image_url)
    else:
      post_images.append(image_url)

  all_data = {
  "title": post_title,
  "topic_id": topic_id,
  "url": url,
  "creator": post_creator,
  "created": date_created,
  "images": post_images,
  "last_updated": last_updated,
  "post_type": post_type
  }
  return all_data

def update_post(post, data):
  post.title = data['title']
  post.topic_id = data['topic_id']
  post.url = data['url']
  post.creator = data['creator']
  post.created = data['created']
  post.last_updated = data['last_updated']
  post.post_type = data['post_type']
  return post

def reset_images(db, db_post, post_all_data, image_model):
  # when len of images don't match, delete images and add again. This way we don't have to compare scrapped url to db url. It also removes the possibility of duplicate images
  print('deleting images')
  images = image_model.query.filter_by(post_id=db_post.id)
  for img in images:
    db.session.delete(img)
    db.session.commit()
  
  print('adding images')
  for img_url in post_all_data['images']:
    new_db_image = image_model(img_url, db_post)
    db.session.add(new_db_image)
    db.session.commit()

def check_post(post_all_data, post_model, image_model, db):
  post_topic_id = int(post_all_data['topic_id'])
  post_time = post_all_data['last_updated']

  db_post = post_model.query.filter_by(topic_id=post_topic_id).first()
  # checking to see if post exists in database
  if db_post:
    print(f"checking {db_post.title}")
    db_post_time = db_post.last_updated
    if db_post_time == post_time and db_post.topic_id == post_topic_id:
      return 1
    else:
      print(f"updating {db_post.title}")
      updated_db_post = update_post(db_post, post_all_data)
      db.session.commit()
      if len(updated_db_post.images) != len(post_all_data['images']):
        reset_images(db, updated_db_post, post_all_data, image_model)
      db.session.close()
      return 0

  # if post doesn't exist in database, add it along with it's images
  else:
    print(f"adding {post_all_data['title']}")
    new_db_post = post_model(post_all_data['title'], post_all_data['topic_id'], post_all_data['url'], post_all_data['creator'], post_all_data['created'], post_all_data['last_updated'], post_all_data['post_type'])
    db.session.add(new_db_post)
    db.session.commit()

    for img_url in post_all_data['images']:
      new_db_image = image_model(img_url, new_db_post)
      db.session.add(new_db_image)
      db.session.commit()
    db.session.close()
    return 0