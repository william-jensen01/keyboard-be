from .extensions import ma
import re


class ImageSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        fields = ("id", "image_url", "order")


class PostSchema(ma.SQLAlchemyAutoSchema):
    images = ma.Method("get_image_urls", dump_only=True)
    title = ma.Method("transform_title", dump_only=True)

    def get_image_urls(self, post):
        adjusted_for_missing_order = [
            {"image_url": image.image_url, "order": image.order or idx, "id": image.id}
            for idx, image in enumerate(post.images)
        ]

        sorted_images = sorted(adjusted_for_missing_order, key=lambda x: x["order"])
        return [image["image_url"] for image in sorted_images]

    def transform_title(self, post):
        # patterns_to_remove = ["[IC]", "【IC】", "[GB]", "【GB】"]

        # # Replace specified patterns
        # title_without_patterns = post.title
        # for pattern in patterns_to_remove:
        #     title_without_patterns = title_without_patterns.replace(pattern, "")

        # # Replace consecutive spaces with a single space
        # title_without_patterns = " ".join(title_without_patterns.split())

        # return title_without_patterns.strip()

        patterns_to_remove = ["\[IC\]", "【IC】", "\[GB\]", "【GB】"]

        # Combine patterns into a single regular expression
        combined_pattern = "|".join(patterns_to_remove)

        # Use regular expression substitution for pattern removal
        title_without_patterns = re.sub(combined_pattern, "", post.title)

        # Replace consecutive spaces with a single space
        title_without_patterns = re.sub(r"\s+", " ", title_without_patterns)

        return title_without_patterns.strip()

    class Meta:
        fields = (
            "id",
            "title",
            "topic_id",
            "url",
            "creator",
            "created",
            "images",
            "last_updated",
            "post_type",
        )


posts_schema = PostSchema(many=True)
post_schema = PostSchema()
images_schema = ImageSchema(many=True)
image_schema = ImageSchema()
