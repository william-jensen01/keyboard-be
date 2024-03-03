from flask import Blueprint, request, jsonify
from src.extensions import db
from src.models import Post, Image
from src.schemas import (
    post_schema,
    posts_schema,
    images_schema,
)
from src.scrape.posts import get_post_data
from src.util import reset_images, handle_pagination

posts = Blueprint("posts", __name__)


@posts.route("/")
def index():
    return jsonify({"message": "Up and well", "ip": request.remote_addr}), 200


# get posts that match search query
@posts.route("/search", methods=["GET"])
# query is included within json body
# limit is coming from url like /posts?limit=10 -- default is 25 if not provided
def get_posts_by_query():
    search_query = request.args.get("query")
    if not search_query:
        return jsonify({"message": "Missing query parameter"}), 400
    limit = request.args.get("limit", 25, type=int)
    page = request.args.get("page", 1, type=int)

    queried_posts, pagination = Post.gets(page=page, per_page=limit, title=search_query)

    page_info = handle_pagination(pagination)
    serialized_posts = posts_schema.dump(queried_posts)

    return jsonify(
        {
            "message": f"Successfully received post of likeness to {search_query}",
            "res": serialized_posts,
            "page_info": page_info,
        }
    )


# get individual post by topic_id
@posts.route("/<topic_id>")
def get_post(topic_id):
    post = Post.get(topic_id=int(topic_id))
    if post:
        post = post_schema.dump(post)
    return jsonify({"message": "Successfully received post", "post": post})


@posts.route("/<topic_id>/images")
def get_post_images(topic_id):
    images = Image.query.filter_by(post_topic_id=topic_id).all()
    if images:
        images = images_schema.dump(images)
    return jsonify(
        {"message": "Successfully received all images for post", "images": images}
    )


@posts.route("/<topic_id>/reset-images")
def rescrape_post(topic_id):
    post = Post.get(
        topic_id=int(topic_id), include_images=False, include_comments=False
    )
    post_url = post.url
    scraped_data = get_post_data(post_url)
    reset_images(post, scraped_data)
    return jsonify({"message": "Successfully rescraped post", "res": scraped_data})


# get posts by post and sort types
@posts.route("/<post_type>/<sort_type>")
# post_type -> 'IC' or 'GB' or 'ALL'
# sort_type -> 'latest' or 'newest'
def get_posts(post_type, sort_type):
    post_type = post_type.upper()
    sort_type = sort_type.lower()
    limit = request.args.get("limit", 25, type=int)
    page = request.args.get("page", 1, type=int)

    # check if post_type is valid
    # if it is either IC GB or ALL
    if post_type == "IC" or post_type == "GB" or post_type == "ALL":
        pass
    else:
        res = jsonify({"error": f"Invalid post type: {post_type}."})
        res.stats_code = 400
        return res

    # check if date_type is valid
    # only valid types are latest and newest
    if sort_type == "latest":
        time = "last_updated"
    elif sort_type == "newest":
        time = "created"
    else:
        res = jsonify({"error": f"Invalid sort type: {sort_type}."})
        res.status_code = 400
        return res

    # if IC or GB include SQL WHERE on post_type
    if post_type == "IC" or post_type == "GB":
        queried_posts, pagination = Post.gets(
            post_type=post_type,
            page=page,
            per_page=limit,
            order_by=time,
            order_dir="desc",
        )

    # post_type is ALL so no need to filter
    else:
        queried_posts, pagination = Post.gets(
            page=page, per_page=limit, order_by=time, order_dir="desc"
        )

    page_info = handle_pagination(pagination)

    res = posts_schema.dump(queried_posts)

    return jsonify(
        {
            "message": f"Successfully received {sort_type} posts - {post_type}",
            "posts": res,
            "page_info": page_info,
        }
    )


# delete post by topic_id
@posts.route("/delete/<topic_id>", methods=["DELETE"])
def delete_post(topic_id):
    post_to_delete = Post.get(
        topic_id=int(topic_id), include_images=False, include_comments=False
    )
    if post_to_delete:
        db.session.delete(post_to_delete)
        db.session.commit()

    return ("", 204)
