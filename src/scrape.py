from bs4 import BeautifulSoup
import requests
import re
from datetime import datetime
import os


# get the last page of a forum
# input is geekhack url with board query
def get_last_page(url):
    req = requests.get(url)
    soup = BeautifulSoup(req.content, "html.parser")
    page_links = soup.find("div", class_="pagelinks floatleft")
    nav_pages = page_links.find_all("a", class_="navPages")
    last_page = nav_pages[-2].text
    return last_page


# get all the data on the forum page for each post (data that is exclusive to that page)
# to do this the whole page much be scrapped as there is no way individually
def get_page_posts_small_data(url):
    """
    Takes in a URL, determines if page is IC or GB by board query
    """
    req = requests.get(url)
    soup = BeautifulSoup(req.content, "html.parser")

    # determine the type of post by parsing the board number from the URL
    post_type = ""
    board_num = re.split("\.|\=", url)[-2]
    if board_num == "132":
        post_type = "IC"
    if board_num == "70":
        post_type = "GB"

    # get all table rows in table body where it has data cell with class 'windowbg2'
    all_posts = soup.select("tbody tr:has(td.windowbg2)")

    small_data = []  # initialize an empty list to store the filtered data

    # for each post get the url, save topic_id from url, create post_url using topic_id, get last_updated stat as datetime, and append post dictionary containing all this data
    for row in all_posts:
        subject_column = row.find("td", class_="subject")
        updated_column = row.find("td", class_="lastpost")
        # contains /index.php?PHPSESSID=...&topic=...
        weird_url = subject_column.find("a").get("href")
        url_parts = re.split("\D+", weird_url)
        topic_id = url_parts[-2]
        post_url = f"https://geekhack.org/index.php?topic={topic_id}.0"

        stats_with_author_list = updated_column.text.split()
        stats_str = " ".join(stats_with_author_list[:5])
        date_format = "%a, %d %B %Y, %H:%M:%S"
        date_time_obj = datetime.strptime(stats_str, date_format)

        # create a new dictionary with the relevant data
        post_small_data = {
            "url": post_url,
            "last_updated": date_time_obj,
            "topic_id": int(topic_id),
            "post_type": post_type,
        }
        small_data.append(post_small_data)
    return small_data


# given a post's url, get the data for that post
def get_post_data(url):
    req = requests.get(url)
    soup = BeautifulSoup(req.content, "html.parser")

    # find the first div element with class 'windowbg'
    # post is always windowbg while the comments alternate windowbg and windowbg2
    # for example
    # first comment is windowbg2
    # second comment is windowbg
    windowbg = soup.find("div", class_="windowbg")
    if not windowbg:
        return
    post_container = windowbg.find("div", class_="post")

    poster_container = windowbg.find("div", class_="poster")
    body = post_container.find("div", class_="inner")

    post_title = windowbg.find("h5").find("a").text.strip()

    post_creator = (
        poster_container.find("h4").text.replace(f"\n", "").replace(f"\t", "")
    )

    date_created_reference_list = soup.find("div", class_="smalltext").text.split()
    created_str = " ".join(date_created_reference_list[2:7])
    date_format = "%a, %d %B %Y, %H:%M:%S"
    date_time_obj = datetime.strptime(created_str, date_format)

    post_images = []
    images = post_container.find_all("img")
    for image in images:
        image_url = image.get("src")
        # if url is geekhack, remove PHPSESSID from url
        if image_url.startswith("https://geekhack.org"):
            split_url = re.split("\?|&", image_url)  # split the url by ? and &
            new_url = f"{split_url[0]}?{split_url[2]}"  # create new url but leave phpsessid part out
            post_images.append(new_url)
        # if url starts with cdn.geekhack, don't add it because it's an emoji
        # there are 2 different urls for geekhack 'images' -- cdn.geekhack (emojis - yes, they count as images) and geekhack (normal images)
        # if image url is cdn.geekhack -> pass as it is most likely an emoji
        elif image_url.startswith("https://cdn.geekhack.org"):
            pass
        # if url is from discord split and if specific index isn't 'attachments' don't add it
        elif image_url.startswith("https://cdn.discordapp"):
            split_url = image_url.split("/")
            if split_url[3] == "attachments":
                post_images.append(image_url)
        else:
            post_images.append(image_url)

    if len(post_images) == 0:
        offsite_images = []
        links = post_container.find_all("a")
        for link in links:
            href = link.get("href")
            domain = href.split("/")[2]
            if domain == "imgur.com":
                imgur_images = scrape_imgur(href)
                offsite_images.extend(imgur_images)
        print("no images here")
        post_images = offsite_images
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
        "last_updated": small_data["last_updated"],
        "url": small_data["url"],
        "topic_id": small_data["topic_id"],
        "post_type": small_data["post_type"],
        "title": post_data["title"],
        "creator": post_data["creator"],
        "created": post_data["created"],
        "images": post_data["images"],
    }


def scrape_imgur(url):
    album_hash = url.split("/")[4]
    client_id = os.environ["IMGUR_CLIENT_ID"]
    req = requests.get(
        f"https://api.imgur.com/3/album/{album_hash}/images",
        headers={"Authorization": f"Client-ID {client_id}"},
    )
    images = [image["link"] for image in req.json()["data"]]
    return images
