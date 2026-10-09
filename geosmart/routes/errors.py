"""Application error handlers."""

from flask import render_template

from geosmart.app_core import app
@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404

