from bs4 import BeautifulSoup
import requests
import re
from datetime import datetime
from .models import Post, Image
from .extensions import db
from sqlalchemy.exc import IntegrityError

# get the last page of a forum
# input is geekhack url with board query
def get_last_page(url):
  req = requests.get(url)
  soup = BeautifulSoup(req.content, 'html.parser')
  page_links = soup.find('div', class_="pagelinks floatleft")
  nav_pages = page_links.find_all('a', class_="navPages")
  last_page = nav_pages[-2].text
  return last_page

# get all the data on the forum page for each post (data that is exclusive to that page)
# to do this the whole page much be scrapped as there is no way individually
def get_page_posts_small_data(url):
  """
  Takes in a URL, determines if page is IC or GB by board query
  """
  req = requests.get(url)
  soup = BeautifulSoup(req.content, 'html.parser')

  # determine the type of post by parsing the board number from the URL
  post_type = ''
  board_num = re.split('\.|\=', url)[-2]
  if board_num == '132':
    post_type = 'IC'
  if board_num == '70':
    post_type = 'GB'

  # get all table rows in table body where it has data cell with class 'windowbg2'
  all_posts = soup.select('tbody tr:has(td.windowbg2)');

  small_data = [] # initialize an empty list to store the filtered data
  
  # for each post get the url, save topic_id from url, create post_url using topic_id, get last_updated stat as datetime, and append post dictionary containing all this data
  for row in all_posts:
    subject_column = row.find('td', class_="subject")
    updated_column = row.find('td', class_="lastpost")
    # contains /index.php?PHPSESSID=...&topic=...
    weird_url = subject_column.find('a').get('href')
    url_parts = re.split('\D+', weird_url)
    topic_id = url_parts[-2]
    post_url = f'https://geekhack.org/index.php?topic={topic_id}.0'

    stats_with_author_list = updated_column.text.split()
    stats_str = ' '.join(stats_with_author_list[:5])
    date_format = "%a, %d %B %Y, %H:%M:%S"
    date_time_obj = datetime.strptime(stats_str, date_format)

    # create a new dictionary with the relevant data
    post_small_data = {
      'url': post_url,
      'last_updated': date_time_obj,
      'topic_id': int(topic_id),
      'post_type': post_type
    }
    small_data.append(post_small_data)
  return small_data

# given a post's url, get the data for that post
def get_post_data(url):
  req = requests.get(url)
  soup = BeautifulSoup(req.content, 'html.parser')

  post_container = soup.find('div', class_="postarea")
  poster_container = soup.find('div', class_="poster")

  post_title = soup.find('h5').text.replace(f"\n", '').lstrip()

  post_creator = poster_container.find('h4').text.replace(f"\n", '').replace(f"\t", '')

  date_created_reference_list = soup.find('div', class_="smalltext").text.split()
  created_str = ' '.join(date_created_reference_list[2:7])
  date_format = "%a, %d %B %Y, %H:%M:%S"
  date_time_obj = datetime.strptime(created_str, date_format)

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
    # if image url is cdn.geekhack -> pass as it is most likely an emoji
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
  "creator": post_creator,
  "created": date_time_obj,
  "images": post_images,
  }
  return all_data

# given both small and regular post data, combine them to have all data for that post
def get_all_post_data(small_data, post_data):
  return {
    "last_updated": small_data['last_updated'],
    "url": small_data['url'],
    "topic_id": small_data['topic_id'],
    "post_type": small_data['post_type'],
    "title": post_data['title'],
    "creator": post_data['creator'],
    "created": post_data['created'],
    "images": post_data['images'],
  }

def update_post(post, data):
  post.topic_id = data['topic_id']
  post.title = data['title']
  post.url = data['url']
  post.creator = data['creator']
  post.created = data['created']
  post.last_updated = data['last_updated']
  post.post_type = data['post_type']
  return post

def reset_images(db_post, post_all_data):
  print('resetting images')

  images = Image.query.filter_by(post_topic_id=db_post.topic_id)
  for img in images:
    db.session.delete(img)
    db.session.commit()
  
  for img_url in post_all_data['images']:
    new_db_image = Image(img_url, db_post)
    db.session.add(new_db_image)
    db.session.commit()

# check if post already exists in db
# post exist -> check if last_updated matches db post
#   matches -> return 1
#   doesn't match -> update db post to reflect new last_updated
# post doesn't exist -> add into db along with its images
def check_post(post_all_data):
  """
  Check if post exists in db
  If post exists -> compare post.last_updated to db post.last_updated
    matches -> return 1
    doesn't match -> update db post and reset it's images
  post doesn't exist -> add into db along with its images
  """
  post_topic_id = int(post_all_data['topic_id'])
  post_time = post_all_data['last_updated']

  print(f"checking {post_all_data['title']}")

  db_post = Post.query.filter_by(topic_id=post_topic_id).first()
  # checking to see if post exists in database
  if db_post:
    db_post_time = db_post.last_updated
    if db_post_time == post_time and db_post.topic_id == post_topic_id:
      print('FOUND MATCH')
      return 1
    else:
      print("updating ^")
      updated_db_post = update_post(db_post, post_all_data)
      db.session.commit()

      # We want to reset the images everytime a post needs to be updated because what if a post previously had 5 images but the designer decided to update all 5 images with better renderings
      reset_images(updated_db_post, post_all_data)
      
      db.session.close()
      return 0

  # since post doesn't exist, add it along with its images
  else:
    print("adding ^")
    new_db_post = Post(topic_id=post_all_data['topic_id'], title=post_all_data['title'], url=post_all_data['url'], creator=post_all_data['creator'], created=post_all_data['created'], last_updated=post_all_data['last_updated'], post_type=post_all_data['post_type'])
    db.session.add(new_db_post)
    db.session.commit()

    for img_url in post_all_data['images']:
      new_db_image = Image(img_url, new_db_post)
      db.session.add(new_db_image)
      db.session.commit()
    db.session.close()
    return 0
  
def populate_helper(post_type, url):
  last_page = get_last_page(url)

  count = 0
  for i in range(1, int(last_page) + 1):
    print(f"starting scraping {i} of {last_page} - {post_type}")
    current_url = f"{url}{count}"
    small_page_data = get_page_posts_small_data(current_url)
    for post_small_data in small_page_data:
      # get full data exclusive to post page and combine it with small_data for the end result of post_all_data
      post_data = get_post_data(post_small_data['url'])
      post_all_data = get_all_post_data(post_small_data, post_data)
      
      print(f"working on {post_all_data['title']}")
      
      # add post to db
      new_db_post = Post(topic_id=post_all_data['topic_id'], title=post_all_data['title'], url=post_all_data['url'], creator=post_all_data['creator'], created=post_all_data['created'], last_updated=post_all_data['last_updated'], post_type=post_all_data['post_type'])

      try:
        db.session.add(new_db_post)
        db.session.commit()
      except IntegrityError as e:
        if "duplicate key value violates unique constraint" in str(e):
          db.session.rollback()
          print('skipping ^')
          continue
        else:
          raise

      print('adding images')

      for img in post_data['images']:
        new_db_image = Image(img, new_db_post)
        db.session.add(new_db_image)
      
      db.session.commit()


    count += 50
    print(f"finished scraping {i} of {last_page} - {post_type}")
  return