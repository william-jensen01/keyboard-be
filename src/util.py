from .models import Post, Image, Comment
from .extensions import db
from .scrape.posts import (
    get_last_page,
    get_page_posts_small_data,
    get_post_data,
    get_all_post_data,
)
from .scrape.comments import (
    get_last_page_count,
    scrape_page_comments,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


def handle_pagination(pagination):
    return {
        "current_page": pagination.page,
        "total_pages": pagination.pages,
        "has_prev": pagination.has_prev,
        "has_next": pagination.has_next,
        "page_range": list(pagination.iter_pages()),
    }


def update_post(db_post, data):
    db_post.topic_id = data["topic_id"]
    db_post.title = data["title"]
    db_post.url = data["url"]
    db_post.creator = data["creator"]
    db_post.created = data["created"]
    db_post.last_updated = data["last_updated"]
    db_post.post_type = data["post_type"]
    db_post.body = data["body"]
    return db_post


def bulk_insert_images(db_post, post_all_data):
    new_images = [
        Image(image_url=img_url, order=idx, post=db_post)
        for idx, img_url in enumerate(post_all_data["images"])
    ]
    db.session.bulk_save_objects(new_images)


def reset_images(db_post, post_all_data):
    print("resetting images")
    # Delete existing images in bulk
    Image.query.filter_by(post_topic_id=db_post.topic_id).delete()
    db.session.commit()
    # Bulk insert new images
    bulk_insert_images(db_post, post_all_data)
    db.session.commit()


def process_post(post_all_data):
    """
    Check if post exists in db
    If post exists -> compare post.last_updated to db post.last_updated
      matches -> return True
      doesn't match -> update db post and reset it's images
    post doesn't exist -> add into db along with its images
    """
    post_topic_id = int(post_all_data["topic_id"])
    post_time = post_all_data["last_updated"]

    print(f"checking {post_all_data['title']}")

    db_post = Post.query.filter_by(topic_id=post_topic_id).first()
    # checking to see if post exists in database
    if db_post:
        db_post_time = db_post.last_updated
        if db_post_time == post_time and db_post.topic_id == post_topic_id:
            print("FOUND MATCH")
            return True
        else:
            print("updating ^")
            try:
                updated_db_post = update_post(db_post, post_all_data)
                # We want to reset the images everytime a post needs to be updated because what if a post previously had 5 images but the designer decided to update all 5 images with better renderings
                reset_images(updated_db_post, post_all_data)
                db.session.commit()
            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Error updating {post_all_data['title']}: {e}")
            finally:
                db.session.close()

    else:
        # add post with its images
        print("adding ^")
        try:
            new_db_post = Post(
                topic_id=post_all_data["topic_id"],
                title=post_all_data["title"],
                url=post_all_data["url"],
                creator=post_all_data["creator"],
                created=post_all_data["created"],
                last_updated=post_all_data["last_updated"],
                post_type=post_all_data["post_type"],
                body=post_all_data["body"],
            )
            db.session.add(new_db_post)
            db.session.commit()

            bulk_insert_images(new_db_post, post_all_data)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"Error adding {post_all_data['title']}: {e}")
        finally:
            db.session.close()
    return False


def process_post_comments(topic_id):
    try:
        # get the last page count
        last_page_count = get_last_page_count(topic_id)

        # get lastest comment
        queried_comment = (
            Comment.query.filter_by(post_topic_id=topic_id)
            .order_by(Comment.number.desc())
            .first()
        )
        comments_to_insert = []
        number = last_page_count
        stop_processing = False

        while number >= 0 and not stop_processing:
            print(f"Working on {number}")

            reversed_comments = scrape_page_comments(topic_id, number)[::-1]

            for comment in reversed_comments:
                print(comment["number"])
                if queried_comment and comment["number"] == queried_comment.number:
                    print("found...stopping")
                    stop_processing = True
                    break
                else:
                    print("adding comment")
                    new_db_comment = Comment(
                        comment_id=comment["comment_id"],
                        post_topic_id=topic_id,
                        number=comment["number"],
                        link=comment["link"],
                        commenter=comment["commenter"],
                        message=comment["message"],
                        is_starter=comment["is_starter"],
                        attachment=comment["attachment"],
                        created_at=comment["created_at"],
                    )
                    comments_to_insert.append(new_db_comment)
            number -= 50
        else:
            # if the loop completes without meeting the condition
            print("Ended up scraping all comments")

        if comments_to_insert:
            db.session.bulk_save_objects(comments_to_insert)
            db.session.commit()
        else:
            print("No comments to insert")
    except Exception as e:
        raise


def populate_helper(post_type, url):
    last_page = get_last_page(url)

    count = 0
    for i in range(1, int(last_page) + 1):
        print(f"starting scraping {i} of {last_page} - {post_type}")
        current_url = f"{url}{count}"
        small_page_data = get_page_posts_small_data(current_url)
        for post_small_data in small_page_data:
            # get full data exclusive to post page and combine it with small_data for the end result of post_all_data
            post_data = get_post_data(post_small_data["url"])
            post_all_data = get_all_post_data(post_small_data, post_data)

            print(f"working on {post_all_data['title']}")

            # add post to db
            new_db_post = Post(
                topic_id=post_all_data["topic_id"],
                title=post_all_data["title"],
                url=post_all_data["url"],
                creator=post_all_data["creator"],
                created=post_all_data["created"],
                last_updated=post_all_data["last_updated"],
                post_type=post_all_data["post_type"],
                body=post_all_data["body"],
            )

            try:
                db.session.add(new_db_post)
                db.session.commit()
            except IntegrityError as e:
                if "duplicate key value violates unique constraint" in str(e):
                    db.session.rollback()
                    print("skipping ^")
                    continue
                else:
                    raise

            print("adding images")

            for img in post_data["images"]:
                new_db_image = Image(img, new_db_post)
                db.session.add(new_db_image)

            db.session.commit()

        count += 50
        print(f"finished scraping {i} of {last_page} - {post_type}")
    return
