from __future__ import annotations

from flask import Flask, send_from_directory

from service.flask.routes.auth import auth_bp
from service.flask.routes.customer import customer_bp
from service.flask.routes.predict import predict_bp
from service.flask.routes.repair import repair_bp
from service.flask.routes.stats import stats_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(predict_bp)
    app.register_blueprint(repair_bp)
    app.register_blueprint(stats_bp)

    @app.get("/")
    def dashboard():
        return send_from_directory("dashboard", "index.html")

    @app.get("/login")
    def login_page():
        return send_from_directory("dashboard", "login.html")

    @app.get("/dashboard/<path:filename>")
    def dashboard_assets(filename: str):
        return send_from_directory("dashboard", filename)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)
