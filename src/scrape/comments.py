from bs4 import BeautifulSoup, Tag, NavigableString
import requests
import re
from datetime import datetime


def clean_creator(creator):
    return creator.replace(f"\n", "").replace(f"\t", "")


def parse_comment_date(date):
    reply_date_reference_list = date.split()
    reply_date_str = " ".join(reply_date_reference_list[4:9])
    date_format = "%a, %d %B %Y, %H:%M:%S"
    return datetime.strptime(reply_date_str, date_format)


def decompose_container(container):
    for header in container.find_all("div", class_="quoteheader"):
        header.decompose()
    for block in container.find_all("blockquote"):
        block.decompose()
    for footer in container.find_all("div", class_="quotefooter"):
        footer.decompose()


def parse_quote_header(quote_header):
    if quote_header:
        info = {}
        header_text = quote_header.text
        split_text = header_text.split()
        if len(split_text) == 1:
            info["commenter"] = None
            info["created_at"] = None
        else:
            try:
                # date/created_at
                date_list = split_text[-5:]
                quote_date = " ".join(date_list).strip()
                date_format = "%a, %d %B %Y, %H:%M:%S"
                quote_datetime = datetime.strptime(quote_date, date_format)
                info["created_at"] = quote_datetime

                # commenter
                quote_creator = " ".join(split_text[2:-6])
                info["commenter"] = quote_creator
            except Exception as err:
                info["commenter"] = None

                # it's possible that header_text is in the following format
                # Quote from: ___ post_id=___ time=___ user_id=___

                pattern = r"time=(\d+)"
                match = re.search(pattern, header_text)
                if match:
                    timestamp = int(match.group(1))
                    info["created_at"] = datetime.fromtimestamp(timestamp)
                else:
                    info["created_at"] = None

        if info["created_at"] is not None:
            info["created_at"] = info["created_at"].isoformat()
        return info


def remove_tags(container):
    if not container:
        return None

    pattern = r"^<[^>]+>|<[^>]+>$"
    result = re.sub(pattern, "", str(container))
    return result


def parse_message(container, decompose=False):
    message_items = []
    for item in container.contents:
        if (
            item.name == "div"
            and item.has_attr("class")
            and "quoteheader" in item["class"]
        ):
            quote_info = parse_quote_header(item)
            continue
        elif item.name == "blockquote":
            message = parse_message(item, decompose=True)
            if decompose:
                decompose_container(item)
            quote_info["message"] = message

            message_items.append(quote_info)
        elif (
            item.name == "div"
            and item.has_attr("class")
            and "quotefooter" in item["class"]
        ):
            continue
        else:
            if isinstance(item, Tag):
                message_items.append(str(item))
            elif isinstance(item, NavigableString):
                uni_string = str(item.string)
                message_items.append(uni_string)
            else:
                message_items.append(str(item))

    return message_items


def parse_quote(blockquote):
    if not blockquote:
        return None

    message_items = parse_message(blockquote, True)
    return message_items


def scrape_comment(wrapper, post_topic_id):
    poster_container = wrapper.find("div", class_="poster")
    commenter = clean_creator(wrapper.find("div", class_="poster").find("h4").text)
    # determines whether or not comment poster is topic post starter
    is_starter = bool(poster_container.find("li", class_="threadstarter"))

    # extract date
    key_info_container = wrapper.find("div", class_="keyinfo")
    key_text = key_info_container.find("div", class_="smalltext").text
    number = key_text.split()[2][1:]

    converted_date = parse_comment_date(key_text).isoformat()

    inner = wrapper.find("div", class_="inner")
    comment_id = inner.get("id").split("_")[-1]

    message_items = parse_message(inner)

    comment_info = {
        "commenter": commenter,
        "is_starter": is_starter,
        "created_at": converted_date,
        "number": int(number),
        "comment_id": int(comment_id),
        "attachment": None,
        "message": message_items,
        "link": f"https://geekhack.org/index.php?topic={post_topic_id}.msg{comment_id}#msg{comment_id}",
    }

    attachment_container = wrapper.find("div", class_="attachments")
    if attachment_container:
        comment_info["attachment"] = remove_tags(attachment_container.div)

    return comment_info


# scrape comment pages
def scrape_page_comments(topic_id, count):
    url = f"https://geekhack.org/index.php?topic={topic_id}.{count}"
    req = requests.get(url)
    soup = BeautifulSoup(req.content, "html5lib")
    global page_soup
    page_soup = soup
    post_wrappers = soup.find_all("div", class_="post_wrapper")
    if count == 0:
        post_wrappers = post_wrappers[1:]
    comments = []
    for wrapper in post_wrappers:
        comments.append(scrape_comment(wrapper, topic_id))

    return comments


def scrape_for_specific_comment(topic_id, comment_number):
    page = comment_number // 50
    url_count = page * 50

    url = f"https://geekhack.org/index.php?topic={topic_id}.{url_count}"
    req = requests.get(url)
    soup = BeautifulSoup(req.content, "html.parser")

    tag = soup.find("strong", text=f"Reply #{comment_number} on:")
    if tag is None:
        return None

    # .parent -> "smalltext"
    # x2.parent -> "keyinfo"
    # x3.parent -> "flow_hidden"
    # x4.parent -> "postarea"
    # x5.parent -> "post_wrapper"
    comment_wrapper = tag.parent.parent.parent.parent.parent
    return scrape_comment(comment_wrapper, topic_id)


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


def scrape_all_comments(topic_id):
    last_page_count = get_last_page_count(topic_id)
    url_count = 0

    comments = []
    while url_count <= int(last_page_count):
        comments.extend(scrape_page_comments(topic_id, url_count))
        url_count += 50

    return comments


def scrape_until(topic_id, limit=None, from_page=1, to_page=None):
    comments = []
    total_comments = 0
    page_count = from_page

    if to_page is not None:
        last_page = to_page
    else:
        last_page = get_last_page_count(topic_id) // 50 + 1

    while page_count <= last_page:
        url_count = (page_count - 1) * 50
        page_comments = scrape_page_comments(topic_id, url_count)

        if limit is not None:
            if total_comments + len(page_comments) > limit:
                page_comments = page_comments[: limit - total_comments]
                comments.extend(page_comments)
                break

        comments.extend(page_comments)
        total_comments += len(page_comments)
        page_count += 1

    return comments
