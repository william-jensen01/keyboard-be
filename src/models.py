from .extensions import db


class Post(db.Model):
    topic_id = db.Column(db.Integer, primary_key=True, nullable=False)
    title = db.Column(db.Text, nullable=False)
    url = db.Column(db.Text, nullable=False)
    creator = db.Column(db.Text, nullable=False)
    created = db.Column(db.DateTime, nullable=False)
    last_updated = db.Column(db.DateTime, nullable=False)
    post_type = db.Column(db.String(2), nullable=False)

    images = db.relationship(
        "Image", cascade="all,delete", backref="post", order_by="asc(Image.order)"
    )

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
    post_topic_id = db.Column(db.Integer, db.ForeignKey("post.topic_id"))
    order = db.Column(db.SmallInteger)

    def __init__(self, image_url, order, post):
        self.image_url = image_url
        self.order = order
        self.post_topic_id = post.topic_id
