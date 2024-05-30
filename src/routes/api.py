from flask import Blueprint, request, jsonify

from src.util import process_post, process_post_comments
from src.scrape.posts import (
    get_all_post_data,
    get_page_posts_small_data,
    get_post_data,
)

posts = Blueprint("posts", __name__)

api = Blueprint("api", __name__)


@api.route("/")
def index():
    return jsonify({"message": "Up and well", "ip": request.remote_addr}), 200


# update db by post_type
@api.route("/update/<post_type>")
def update(post_type):
    post_type = post_type.upper()

    limit = request.args.get("limit", type=int)
    if limit is not None:
        try:
            limit = int(limit)
        except Exception as e:
            print(e)
            return jsonify({"message": "Limit is invalid - must be an integer."})

    def scrape_posts_cross_pages(url):
        stop_processing = False
        count = 0
        while not stop_processing:
            print(f"Begin scraping .{count} (page {(count // 50) + 1})")
            current_url = f"{url}.{count}"
            page_small_data = get_page_posts_small_data(current_url)

            for idx, small_post_data in enumerate(page_small_data):
                print(
                    f"post: {small_post_data['topic_id']} -- {(count // 50) + 1}.{idx + 1}"
                )
                post_data = get_post_data(small_post_data["url"])
                all_post_data = get_all_post_data(small_post_data, post_data)
                stop_processing = process_post(all_post_data)
                # stop_processing = False
                process_post_comments(all_post_data["topic_id"])

                if limit is not None and (idx + count) >= limit - 1:
                    print("STOPPING because limit has been reached")
                    stop_processing = True
                    break
                elif limit is None and stop_processing:
                    print("STOPPING")
                    stop_processing = True
                    break

                print("------")

            print(f"Finished scraping .{count} (page {(count // 50) + 1})\n")
            count += 50

    if post_type == "IC" or post_type == "GB" or post_type == "DB":
        if post_type == "IC":
            print("\nWorking on IC\n")
            url = "https://geekhack.org/index.php?board=132"
            scrape_posts_cross_pages(url)

        if post_type == "GB":
            print("\nWorking on GB\n")
            url = "https://geekhack.org/index.php?board=70"
            scrape_posts_cross_pages(url)

        if post_type == "DB":
            update("IC")
            update("GB")
    else:
        res = jsonify({"message": f"Invalid post_type: {post_type}"})
        res.status_code = 400
        return res

    return jsonify({"message": f"Successfully updated {post_type}."})
