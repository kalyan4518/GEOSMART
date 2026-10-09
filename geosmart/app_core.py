"""Shared Flask application instance and root-relative asset configuration."""

from flask import Flask

from geosmart.config import BASE_DIR, Config

app = Flask(
    "geosmart",
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.secret_key = Config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
