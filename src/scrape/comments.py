from bs4 import BeautifulSoup
import requests
import re
from datetime import datetime
from src.models import Comment


def clean_creator(creator):
    return creator.replace(f"\n", "").replace(f"\t", "")


def convert_to_datetime(date):
    reply_date_reference_list = date.split()
    reply_date_str = " ".join(reply_date_reference_list[4:9])
    date_format = "%a, %d %B %Y, %H:%M:%S"
    return datetime.strptime(reply_date_str, date_format)


def get_comment_info(wrapper):
    poster_container = wrapper.find("div", class_="poster")
    commenter = clean_creator(wrapper.find("div", class_="poster").find("h4").text)
    # determines whether or not comment poster is topic post starter
    is_starter = bool(poster_container.find("li", class_="threadstarter"))

    # extract date
    key_info_container = wrapper.find("div", class_="keyinfo")
    key_text = key_info_container.find("div", class_="smalltext").text
    number = key_text.split()[2][1:]

    converted_date = convert_to_datetime(key_text)

    comment_id = wrapper.find("div", class_="inner").get("id").split("_")[-1]

    return {
        "commenter": commenter,
        "is_starter": is_starter,
        "created_at": converted_date,
        "number": int(number),
        "comment_id": int(comment_id),
    }


def decompose_container(container):
    for header in container.find_all("div", class_="quoteheader"):
        header.decompose()
    for block in container.find_all("blockquote"):
        block.decompose()
    for footer in container.find_all("div", class_="quotefooter"):
        footer.decompose()


def parse_quote_header(quote_container):
    header = quote_container.find("div", class_="quoteheader")
    if header:
        info = {}
        header_text = header.text
        split_text = header_text.split()
        if len(split_text) == 1:
            info["commenter"] = None
            info["created_at"] = None
        else:
            # commenter
            quote_creator = " ".join(split_text[2:-6])
            info["commenter"] = quote_creator

            # date/created_at
            date_list = split_text[-5:]
            quote_date = " ".join(date_list).strip()
            date_format = "%a, %d %B %Y, %H:%M:%S"
            quote_datetime = datetime.strptime(quote_date, date_format)
            info["created_at"] = quote_datetime

        return info


def remove_tags(container):
    if not container:
        return None

    pattern = r"^<[^>]+>|<[^>]+>$"
    result = re.sub(pattern, "", str(container))
    return result


def parse_quote(blockquote):
    if not blockquote:
        return None

    header_info = parse_quote_header(blockquote.parent)

    quote_info = {}
    quote_info.update(header_info)

    nested_header = blockquote.find("div", class_="quoteheader")

    if nested_header:
        nested_blockquote = blockquote.find("blockquote")

        if nested_blockquote:
            nested_info = parse_quote(nested_blockquote)
            quote_info["is_reply_to_quote"] = True
            quote_info["quote_info"] = nested_info

    decompose_container(blockquote)
    quote_info["message"] = remove_tags(blockquote)

    return quote_info


# determines if a comment is a reply to another comment
def parse_comment(wrapper):
    container = wrapper.find("div", class_="inner")
    contents = container.contents
    items = []
    is_reply_to_quote = False
    for item in contents:
        if (
            item.name == "div"
            and item.has_attr("class")
            and "quoteheader" in item["class"]
        ):
            continue
        elif item.name == "blockquote":
            quote_info = parse_quote(item)
            is_reply_to_quote = True
            items.append(quote_info)
        elif (
            item.name == "div"
            and item.has_attr("class")
            and "quotefooter" in item["class"]
        ):
            continue
        else:
            items.append(item)

    comment_info = {
        "attachment": None,
        "message": items,
        "is_reply_to_quote": is_reply_to_quote,
    }

    attachment_container = wrapper.find("div", class_="attachments")
    if attachment_container:
        comment_info["attachment"] = remove_tags(attachment_container.div)

    return comment_info


# scrape comment pages
def scrape_page_comments(topic_id, count):
    url = f"https://geekhack.org/index.php?topic={topic_id}.{count}"
    req = requests.get(url)
    soup = BeautifulSoup(req.content, "html.parser")
    global page_soup
    page_soup = soup
    post_wrappers = soup.find_all("div", class_="post_wrapper")
    if count == 0:
        post_wrappers = post_wrappers[1:]
    comments = []
    for post in post_wrappers:
        basic_comment_info = get_comment_info(post)
        # create link to comment using topic_id and comment_id
        comment_id = basic_comment_info["comment_id"]
        basic_comment_info["link"] = (
            f"https://geekhack.org/index.php?topic={topic_id}.msg{comment_id}#msg{comment_id}"
        )

        comment_information = parse_comment(post)
        comment_information.update(basic_comment_info)

        comments.append(comment_information)

    return comments


def get_last_page_count(topic_id):
    base_url = f"https://geekhack.org/index.php?topic={topic_id}.0"
    req = requests.get(base_url)
    soup = BeautifulSoup(req.content, "html.parser")

    # go to last page
    page_links_container = soup.find("div", class_="pagelinks")
    nav_pages = page_links_container.find_all("a", class_="navPages")
    if len(nav_pages) >= 2:
        return int(nav_pages[-2].get("href").split(".")[-1])
    else:
        return 0
