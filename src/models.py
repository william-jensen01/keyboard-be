from .extensions import db

class Post(db.Model):
    topic_id = db.Column(db.Integer, primary_key=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    creator = db.Column(db.String(50), nullable=False)
    created = db.Column(db.DateTime, nullable=False)
    last_updated = db.Column(db.DateTime, nullable=False)
    post_type = db.Column(db.String(5), nullable=False)

    images = db.relationship('Image', cascade="all,delete", backref='post')


    def __init__(self, title, topic_id, url, creator, created, last_updated, post_type):
        self.topic_id = topic_id
        self.title = title
        self.url = url
        self.creator = creator
        self.created = created
        self.last_updated = last_updated
        self.post_type = post_type


class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.Text)
    post_topic_id = db.Column(db.Integer, db.ForeignKey('post.topic_id'))

    def __init__(self, image_url, post):
        self.image_url = image_url
        self.post = post