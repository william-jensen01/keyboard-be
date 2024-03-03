from flask import Blueprint, request, jsonify
from src.extensions import db
from src.models import Comment
from src.schemas import comment_schema, comments_schema
from src.scrape.comments import (
    scrape_page_comments,
)
from src.util import process_post_comments

comments = Blueprint("comments", __name__)


@comments.route("/")
def index():
    return jsonify({"message": "Up and well", "ip": request.remote_addr}), 200


@comments.route("/<post_topic_id>/update")
def update(post_topic_id):
    try:
        post_topic_id = int(post_topic_id)
    except ValueError:
        return jsonify({"error": "Invalid post_topic_id"}), 400

    try:
        process_post_comments(post_topic_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(
        {"message": f"Successfully updated comments related to {post_topic_id}"}
    )


@comments.route("/commenter/<commenter_name>")
def get_comments_by_commenter(commenter_name):
    if not commenter_name.strip():
        return jsonify({"message": "Missing or empty commenter name"}), 400

    # query where commenter is like commenter_name
    # this allows it be to case-insensitive
    queried_comments = Comment.query.filter(
        Comment.commenter.ilike(commenter_name)
    ).all()

    if not queried_comments:
        return jsonify({"message": f"No comments found from {commenter_name}"}), 404

    comments = comments_schema.dump(queried_comments)

    return jsonify(
        {
            "message": f"Successfully queried comments from {commenter_name}",
            "comments": comments,
        }
    )


@comments.route("/<post_topic_id>/<sort_type>")
def get_comments_from_topic_id(post_topic_id, sort_type="latest"):
    try:
        post_topic_id = int(post_topic_id)
    except ValueError:
        return jsonify({"message": "Invalid type of post topic id"}), 400

    sort_type = sort_type.lower()

    if sort_type != "latest" and sort_type != "newest":
        return jsonify({"message": "Invalid sort type"}), 400

    if sort_type == "latest":
        queried_comments = (
            Comment.query.filter_by(post_topic_id=post_topic_id)
            .order_by(Comment.created_at.desc())
            .all()
        )
    elif sort_type == "newest":
        queried_comments = (
            Comment.query.filter_by(post_topic_id=post_topic_id)
            .order_by(Comment.created_at.asc())
            .all()
        )

    if not queried_comments:
        return (
            jsonify(
                {
                    "message": f"No comments found from {post_topic_id} sorted {sort_type}"
                }
            ),
            404,
        )

    comments = comments_schema.dump(queried_comments)

    return jsonify({"message": "Successfully queried comments", "comments": comments})
