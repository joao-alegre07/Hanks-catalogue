import os

from flask import Flask


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = os.environ["SECRET_KEY"]

    from .auth import auth_bp
    from .movies import movies_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(movies_bp)

    return app
