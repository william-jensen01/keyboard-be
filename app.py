from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from dotenv import load_dotenv
import os

from functions import update_post, get_all_post_data, get_page_posts_small_data, get_last_page, update_db_by_type, check_post

load_dotenv()
app = Flask(__name__)
CORS(app)

app.debug = False
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
    created = db.Column(db.String(40))
    images = db.relationship('Image', backref='post')
    views = db.Column(db.Integer)
    replies = db.Column(db.Integer)
    last_updated = db.Column(db.String(40))
    post_type = db.Column(db.String(5), nullable=False)

    def __init__(self, title, topic_id, url, creator, created, views, replies, last_updated, post_type):
        self.title = title
        self.topic_id = topic_id
        self.url = url
        self.creator = creator
        self.created = created
        self.views = views
        self.replies = replies
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
        fields = ('id', 'image_url', 'post_id')

class PostSchema(ma.SQLAlchemyAutoSchema):
    images = ma.Nested(ImageSchema, many=True)
    class Meta:
        fields = ('id', 'title', 'topic_id', 'url', 'creator', 'created', 'images','views', 'replies', 'last_updated', 'post_type')

posts_schema = PostSchema(many=True)
post_schema = PostSchema()

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

# get all posts by type or add new post to type
@app.route('/api/<post_type>', methods=['GET', 'POST'])
def get_posts(post_type):
    if request.method == 'GET':
        post_type = post_type.upper()
        posts = Post.query.filter_by(post_type=post_type).all()
        if len(posts) > 0:
            output = posts_schema.dump(posts)
            return jsonify({'message': 'Successfully received posts', 'posts': output})
        else:
            res = jsonify({'error': f"{post_type} is not a valid post type"})
            res.status_code = 404
            return res
    if request.method == 'POST':
        data = request.json
        new_db_post = Post(data['title'], data['topic_id'], data['url'], data['creator'], data['created'], data['views'], data['replies'], data['last_updated'], data['post_type'])
        db.session.add(new_db_post)
        db.session.commit()

        for img_url in data['images']:
            new_db_image = Image(img_url, new_db_post)
            db.session.add(new_db_image)
            db.session.commit()
        db.session.close()

        return jsonify({'message': 'Successfully added new post'})

# update db by type
@app.route('/api/update/<post_type>')
def update(post_type):
    post_type = post_type.upper()
    url = ''
    count = 0

    if post_type == 'IC':
        url = 'https://geekhack.org/index.php?board=132.0'
        page_small_data = get_page_posts_small_data(url)
        for post_small_data in page_small_data:
            post_all_data = get_all_post_data(post_small_data, post_type)
            value = check_post(post_all_data, Post, Image, db)
            if value == 1:
                break
            else:
                count += 1

    if post_type == 'GB':
        url = 'https://geekhack.org/index.php?board=70.0'
        page_small_data = get_page_posts_small_data(url)
        for post_small_data in page_small_data:
            post_all_data = get_all_post_data(post_small_data, post_type)
            value = check_post(post_all_data, Post, Image, db)
            if value == 1:
                break
            else:
                count += 1
    if post_type == 'DB':
        update('IC')
        update('GB')
    return jsonify({'message': f"Successfully updated {count + 1} posts."})

if __name__ == "__main__":
    app.run()