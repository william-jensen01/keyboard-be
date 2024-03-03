from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv, find_dotenv

from .extensions import db, ma
from .commands import create_tables
from .routes.api import api as api_bp
from .routes.posts import posts as posts_bp
from .routes.comments import comments as comments_bp


def create_app(config_file="settings.py"):
    load_dotenv(find_dotenv())
    app = Flask(__name__)
    CORS(app)

    app.config.from_pyfile(config_file)

    db.init_app(app)
    ma.init_app(app)

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(posts_bp, url_prefix="/api/posts")
    app.register_blueprint(comments_bp, url_prefix="/api/comments")

    app.cli.add_command(create_tables)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="10.0.0.133")
