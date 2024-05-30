from flask import Blueprint, request, jsonify
from src.models import Comment
from src.schemas import comment_schema, comments_schema
from src.scrape.comments import (
    scrape_page_comments,
    get_last_page_count,
    scrape_for_specific_comment,
    scrape_all_comments,
    scrape_until,
)
from src.util import (
    process_post_comments,
    handle_pagination,
    bulk_insert_comments,
    insert_comment,
)

comments = Blueprint("comments", __name__)


@comments.route("/")
def index():
    return jsonify({"message": "Up and well", "ip": request.remote_addr}), 200


@comments.route("/update/<post_topic_id>")
def update_post_comments(post_topic_id):
    try:
        post_topic_id = int(post_topic_id)
    except Exception as e:
        return jsonify({"error": "Invalid topic_id type - must be an integer"}), 400

    try:
        process_post_comments(post_topic_id)
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500

    return jsonify(
        {"message": f"Successfully updated comments related to {post_topic_id}"}
    )


@comments.route("/scrape/<post_topic_id>")
# mother endpoint for handling comment scraping requests
# allows to scrape comments by post topic id, page number, individual comment number, limit, from specific page, to specific page, and add scraped information to database
# arguments/queries allowed: single, page , limit, add
# does not support chaining multiple number identifiers (page, single)
# does support chaining a number identifier with "add"
# does support chaining page and limit, from page and to page
def scrape_according_to_parameters(post_topic_id):
    single = request.args.get("single", None, type=int)
    limit = request.args.get("limit", None, type=int)
    to_page = request.args.get("to_page", None, type=int)
    from_page = request.args.get("from_page", 1, type=int)
    add = request.args.get("add", False, type=lambda v: v in ["true", "", "1"])

    # convert page query to list of integers
    page_query = request.args.get("page", "")
    try:
        pages = list(map(int, page_query.split(","))) if page_query else []
    except ValueError:
        return jsonify(
            {"error": "Invalid page numbers. Page numbers must be integers."}
        )

    try:
        post_topic_id = int(post_topic_id)
    except ValueError:
        return (
            jsonify(
                {"message": "Invalid parameters - could not convert to an integer."}
            ),
            400,
        )

    result = []

    if single is not None:
        if pages is not None:
            return jsonify({"message": "You cannot include single and page together"})

        url_count = (single // 50) * 50
        last_page_count = get_last_page_count(post_topic_id)

        if url_count > last_page_count:
            return jsonify({"error": "There is no page available for that number"})

        result = scrape_for_specific_comment(post_topic_id, single)
        if not result:
            return jsonify({"error": "That comment does not exist"}), 404
        return result

    elif len(pages) > 0:
        for page_num in pages:
            url_count = (page_num - 1) * 50

            last_page_count = get_last_page_count(post_topic_id)

            if url_count > last_page_count or url_count < 0:
                return jsonify({"error": "That comment page does not exist"})

            result.extend(
                scrape_page_comments(post_topic_id, url_count)[
                    : limit if limit else None
                ]
            )

    elif limit is not None or from_page is not None or to_page is not None:
        result = scrape_until(
            post_topic_id, limit=limit, from_page=from_page, to_page=to_page
        )
    else:
        result = scrape_all_comments(post_topic_id)

    if add:
        if isinstance(result, list):
            bulk_insert_comments(result, post_topic_id)
        elif isinstance(result, dict):
            insert_comment(result, post_topic_id)

    return result


@comments.route("/<post_topic_id>")
# mother endpoint for handling comment querying requests
# allows to query by post topic id, page number, single comment number, and sort by ascending or descending
# arguments/queries allowed: single, sort
# does not support chaining multiple number identifiers (single, sort)
def from_topic_id(post_topic_id):
    single = request.args.get("single", None, type=int)
    sort_type = request.args.get("sort", "asc", type=str).lower()
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 25, type=int)

    try:
        post_topic_id = int(post_topic_id)
    except ValueError as e:
        return (
            jsonify(
                {"message": "Invalid parameters - could not convert to an integer."}
            ),
            400,
        )

    if single is not None:
        queried_comment = (
            Comment.query.filter_by(post_topic_id=post_topic_id, number=single)
            .order_by(getattr(Comment.created_at, sort_type)())
            .first()
        )

        if queried_comment:
            res = comment_schema.dump(queried_comment)
            return jsonify({"message": "Successfully queried", "items": [res]})
        else:
            return (
                jsonify({"message": f"#{single} from {post_topic_id} does not exist."}),
                404,
            )
    else:
        if sort_type != "asc" and sort_type != "desc":
            return jsonify({"message": "Invalid sort type"}), 400

        queried_comments = None

        queried_comments = (
            Comment.query.filter_by(post_topic_id=post_topic_id)
            .order_by(getattr(Comment.created_at, sort_type)())
            .paginate(page=page, per_page=limit)
        )

        comments = comments_schema.dump(queried_comments.items)
        page_info = handle_pagination(queried_comments)

        if not comments:
            return (
                jsonify(
                    {
                        "message": f"No comments found from {post_topic_id} sorted {sort_type}",
                    }
                ),
                404,
            )

        return jsonify(
            {
                "message": "Successfully queried comments",
                "items": comments,
                "page_info": page_info,
            }
        )
