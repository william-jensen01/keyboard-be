from flask import Blueprint, request, jsonify

from src.extensions import db
from src.models import Post, Image
from src.schemas import post_schema

posts = Blueprint('posts', __name__)

@posts.route('/')
def index():
    return jsonify({'message': 'Up and well', 'ip': request.remote_addr}), 200

# add new post into database
# this will only be used when populating for the first time. That's why we aren't checking if any of the information is missing.
@posts.route('/new', methods=['POST'])
def create_post():
    post = request.json
    print(f"adding {post['title']}")

    new_db_post = Post(topic_id=post['title'], title=post['title'], url=post['url'], creator=post['creator'], created=post['created'], last_updated=post['last_updated'], post_type=post['post_type'])
    db.session.add(new_db_post)
    db.session.commit()
    print('adding images')
    for img in post['images']:
        new_db_image = Image(img, new_db_post)
        db.session.add(new_db_image)
        db.session.commit()
    db.session.close()

    return jsonify({'message': f"Successfully added {post['title']} into the system."})

# get posts that match search query
@posts.route('/search', methods=['POST'])
# query is included within json body
# limit is coming from url like /posts?limit=10 -- default is 25 if not provided
def get_posts_by_query():
    search_query = request.json['query']
    limit = request.args.get('limit', 25, type=int)
    page = request.args.get('page', 1, type=int)

    posts = Post.query.filter(Post.title.ilike(f"%{search_query}%")).paginate(page=page, per_page=limit)

    page_info = {
        'current_page': posts.page,
        'total_pages': posts.pages,
        'has_prev': posts.has_prev,
        'has_next': posts.has_next,
        'page_range': list(posts.iter_pages())
    }

    res = [dict(post_schema.dump(post), images=[img.image_url for img in post.images]) for post in posts.items]

    return jsonify({'message': f"Successfully received post of likeness to {search_query}", 'res': res, 'page_info': page_info})

# get individual post by type and topic_id
@posts.route('/<topic_id>')
# post_type -> IC or GB
def get_post(topic_id):
    post = Post.query.filter_by(topic_id=topic_id).first()
    post = [dict(post_schema.dump(post), images=[img.image_url for img in post.images])]

    return jsonify({'message': 'Successfully received post', 'post': post})

#get posts by post and sort types
@posts.route('/<post_type>/<sort_type>')
# post_type -> 'IC' or 'GB' or 'ALL'
# sort_type -> 'latest' or 'newest'
def get_posts(post_type, sort_type):
    post_type = post_type.upper()
    sort_type = sort_type.lower()
    limit = request.args.get('limit', 25, type=int)
    page = request.args.get('page', 1, type=int)

    # check if post_type is valid
    # if it is either IC GB or ALL
    if post_type == 'IC' or post_type == 'GB' or post_type == 'ALL':
        pass
    else:
        res = jsonify({'error': f"Invalid post type: {post_type}."})
        res.stats_code = 400
        return res
    
    # check if date_type is valid
    # only valid types are latest and newest
    if sort_type == 'latest':
        time = 'last_updated'
    elif sort_type == 'newest':
        time = 'created'
    else:
        res = jsonify({'error': f"Invalid sort type: {sort_type}."})
        res.status_code = 400
        return res
    
    # if IC or GB include SQL WHERE on post_type
    if post_type == 'IC' or post_type == 'GB':
        queried_posts = db.session.query(Post).where(Post.post_type == post_type).order_by(getattr(Post, time).desc()).paginate(page=page, per_page=limit)
    
    # post_type is ALL so no need for SQL where
    # just query with .order_by and .paginate
    else:
        queried_posts = db.session.query(Post).order_by(getattr(Post, time).desc()).paginate(page=page, per_page=limit)
    
    page_info = {
        'current_page': queried_posts.page,
        'total_pages': queried_posts.pages,
        'has_prev': queried_posts.has_prev,
        'has_next': queried_posts.has_next,
        'page_range': list(queried_posts.iter_pages())
    }

    # resulting list that contains dictionaries for each post in queried_posts
    # update dictionary['images'] (or post.images) to be list of image_urls which was previously a list of dictionaries of image info
    res = [dict(post_schema.dump(post), images=[img.image_url for img in post.images]) for post in queried_posts.items]

    return jsonify({'message': f"Successfully received {sort_type} posts - {post_type}", 'posts': res, 'page_info': page_info})