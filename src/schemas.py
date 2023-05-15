from .extensions import ma

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