from app.web.views import bp as web_bp


def register_web(app):
    app.register_blueprint(web_bp)
