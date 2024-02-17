from flask import Blueprint, request, jsonify
from src.extensions import db
from src.models import Post, Image
from src.schemas import post_schema, posts_schema, images_schema
from src.scrape import get_post_data
from src.util import reset_images

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

    queried_posts = (
        Post.query.options(db.joinedload(Post.images))
        .filter(Post.title.ilike(f"%{search_query}%"))
        .paginate(page=page, per_page=limit)
    )

    pagination_info = {
        "current_page": queried_posts.page,
        "total_pages": queried_posts.pages,
        "has_prev": queried_posts.has_prev,
        "has_next": queried_posts.has_next,
        "page_range": list(queried_posts.iter_pages()),
    }
    serialized_posts = posts_schema.dump(queried_posts)

    return jsonify(
        {
            "message": f"Successfully received post of likeness to {search_query}",
            "res": serialized_posts,
            "page_info": pagination_info,
        }
    )


# get individual post by topic_id
@posts.route("/<topic_id>")
def get_post(topic_id):
    post = (
        Post.query.options(db.joinedload(Post.images))
        .filter_by(topic_id=topic_id)
        .first()
    )
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


@posts.route("/<topic_id>/scrape")
def rescrape_post(topic_id):
    post = Post.query.filter_by(topic_id=topic_id).first()
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
        queried_posts = (
            Post.query.options(db.joinedload(Post.images))
            .filter_by(post_type=post_type)
            .order_by(getattr(Post, time).desc())
            .paginate(page=page, per_page=limit)
        )

    # post_type is ALL so no need to filter
    else:
        queried_posts = (
            Post.query.options(db.joinedload(Post.images))
            .order_by(getattr(Post, time).desc())
            .paginate(page=page, per_page=limit)
        )

    page_info = {
        "current_page": queried_posts.page,
        "total_pages": queried_posts.pages,
        "has_prev": queried_posts.has_prev,
        "has_next": queried_posts.has_next,
        "page_range": list(queried_posts.iter_pages()),
    }

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
    post_to_delete = (
        Post.query.options(db.joinedload(Post.images))
        .filter_by(topic_id=topic_id)
        .first()
    )
    if post_to_delete:
        db.session.delete(post_to_delete)
        db.session.commit()

    return ("", 204)
