from re import search
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
import os
import math

from functions import update_post, get_all_post_data, get_page_posts_small_data, get_last_page, check_post

app = Flask(__name__)
CORS(app)

app.debug = True
uri = os.getenv('DATABASE_URL')
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS')

db = SQLAlchemy(app)
ma = Marshmallow(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    topic_id = db.Column(db.Integer, nullable=False)
    url = db.Column(db.String(200), nullable=False)
    creator = db.Column(db.String(50), nullable=False)
    created = db.Column(db.String(35))
    images = db.relationship('Image', backref='post')
    last_updated = db.Column(db.String(35))
    post_type = db.Column(db.String(5), nullable=False)

    def __init__(self, title, topic_id, url, creator, created, last_updated, post_type):
        self.title = title
        self.topic_id = topic_id
        self.url = url
        self.creator = creator
        self.created = created
        self.last_updated = last_updated
        self.post_type = post_type


class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(400))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))

    def __init__(self, image_url, post):
        self.image_url = image_url
        self.post = post

class ImageSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        fields = ('id', 'image_url')

class PostSchema(ma.SQLAlchemyAutoSchema):
    images = ma.Nested(ImageSchema, many=True)
    class Meta:
        fields = ('id', 'title', 'topic_id', 'url', 'creator', 'created', 'images', 'last_updated', 'post_type')

posts_schema = PostSchema(many=True)
post_schema = PostSchema()
images_schema = ImageSchema(many=True)
image_schema = ImageSchema()

# add a new post to the db
# this will only be used when populating the db for the first time. That's why we aren't checking if any of the information is missing
@app.route('/api/new', methods=['POST'])
def add_post():
    post = request.json
    print(f"adding {post['title']}")
    new_db_post = Post(post['title'], post['topic_id'], post['url'], post['creator'], post['created'], post['last_updated'], post['post_type'])
    db.session.add(new_db_post)
    db.session.commit()
    print('adding images')
    for img in post['images']:
        new_db_image = Image(img, new_db_post)
        db.session.add(new_db_image)
        db.session.commit()
    db.session.close()
    return jsonify({'message': f"Successfully added {post['title']} into the system"})

# get posts that match search query
@app.route('/api/posts', methods=['POST'])
def get_posts_by_query():
    if request.method == 'POST':
        search_query = request.json['query'].lower()
        limit = request.args.get('limit', 25, type=int)
        posts = db.engine.execute(f"SELECT p.*, array_agg(i.image_url) AS images FROM post p LEFT JOIN image i ON i.post_id = p.id WHERE LOWER(p.title) LIKE '%%{search_query}%%' GROUP BY 1")
        res = [dict(post._mapping.items()) for post in posts]

        num_posts = len(res)
        num_pages = math.ceil(num_posts / limit)

        return jsonify({"message": f"Successfully received posts matching: {search_query}", 'pages': num_pages, 'posts': res})

# get posts by post and date
@app.route('/api/<date_type>/<post_type>')
# date_type -> latest or newest
# post_type -> IC, GB, or All
def get_posts(date_type, post_type):
    post_type = post_type.upper()
    date_type = date_type.lower()
    limit = request.args.get('limit', 25, type=int)
    page = request.args.get('page', 1, type=int)
    start_index = (page-1) * limit

    # check if post_type is valid
    if post_type == 'IC' or post_type == 'GB' or post_type == 'ALL':
        pass
    else:
        res = jsonify({'error': f"Invalid post type: {post_type}"})
        res.status_code = 400
        return res

    # check if date_type is valid
    if date_type == 'latest':
        time = 'last_updated'
    elif date_type == 'newest':
        time = 'created'
    else:
        res = jsonify({'error': f"Invalid date type: {date_type}."})
        res.status_code = 400
        return res

    # if post_type is IC or GB
    if post_type != 'ALL':
        newest_posts = db.engine.execute(f"SELECT p.*, array_agg(i.image_url) AS images FROM post p LEFT JOIN image i ON i.post_id = p.id WHERE p.post_type='{post_type}' GROUP BY 1 ORDER BY SUBSTRING(p.{time}, LENGTH(p.{time}) - 3, 4) DESC, EXTRACT(MONTH FROM to_date(SUBSTRING(p.{time}, 15, LENGTH(p.{time}) - 23), 'Mon')) DESC, SUBSTRING(p.{time}, LENGTH(p.{time}) - 7, 2) DESC, SUBSTRING(p.{time}, 1,8) DESC LIMIT {limit} OFFSET {start_index}")
        num_posts = Post.query.filter_by(post_type=post_type).count()
    elif post_type == 'ALL':
        newest_posts = db.engine.execute(f"SELECT p.*, array_agg(i.image_url) AS images FROM post p LEFT JOIN image i ON i.post_id = p.id GROUP BY 1 ORDER BY SUBSTRING(p.{time}, LENGTH(p.{time}) - 3, 4) DESC, EXTRACT(MONTH FROM to_date(SUBSTRING(p.{time}, 15, LENGTH(p.{time}) - 23), 'Mon')) DESC, SUBSTRING(p.{time}, LENGTH(p.{time}) - 7, 2) DESC, SUBSTRING(p.{time}, 1,8) DESC LIMIT {limit} OFFSET {start_index}")
        num_posts = Post.query.count()

    res = [dict(post._mapping.items()) for post in newest_posts]
    num_pages = math.ceil(num_posts / limit )

    return jsonify({'message': f"Successfully received {date_type} {post_type} posts", 'pages': num_pages, 'posts': res})

# get individual post by type and id
@app.route('/api/<post_type>/<post_id>')
def get_post(post_type, post_id):
    post_type = post_type.upper()
    post = Post.query.filter_by(id=post_id, post_type=post_type).first()
    if post:
        output = post_schema.dump(post)
        return jsonify({'message': 'Successfully received post', 'post': output})
    else:
        res = jsonify({'error': f"{post_type} Post with specified id or type does not exist."})
        res.status_code = 404
        return res

# update db by type
@app.route('/api/update/<post_type>')
def update(post_type):
    post_type = post_type.upper()
    url = ''

    if post_type == 'IC':
        url = 'https://geekhack.org/index.php?board=132.0'
        page_small_data = get_page_posts_small_data(url)
        for post_small_data in page_small_data:
            post_all_data = get_all_post_data(post_small_data)
            value = check_post(post_all_data, Post, Image, db)
            if value == 1:
                break

    if post_type == 'GB':
        url = 'https://geekhack.org/index.php?board=70.0'
        page_small_data = get_page_posts_small_data(url)
        for post_small_data in page_small_data:
            post_all_data = get_all_post_data(post_small_data)
            value = check_post(post_all_data, Post, Image, db)
            if value == 1:
                break

    if post_type == 'DB':
        update('IC')
        update('GB')

    return jsonify({'message': f"Successfully updated {post_type}."})

if __name__ == "__main__":
    app.run()