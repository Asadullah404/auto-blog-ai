"""Package initialization for web REST API blueprints."""
from flask import Flask

from web.api.pipeline_api import pipeline_bp
from web.api.settings_api import settings_bp
from web.api.wordpress_api import wordpress_bp
from web.api.queue_api import queue_bp
from web.api.articles_api import articles_bp
from web.api.skills_api import skills_bp
from web.api.logs_api import logs_bp


def register_api_blueprints(app: Flask) -> None:
    """Registers all application API blueprints onto the main Flask application."""
    app.register_blueprint(pipeline_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(wordpress_bp)
    app.register_blueprint(queue_bp)
    app.register_blueprint(articles_bp)
    app.register_blueprint(skills_bp)
    app.register_blueprint(logs_bp)
