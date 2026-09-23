import os

from flask import Flask, request

from .auditoria import registrar


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = os.environ["SECRET_KEY"]

    from .auth import auth_bp
    from .movies import movies_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(movies_bp)

    # Todo 403 do catálogo passa por aqui, então nenhuma tentativa negada
    # escapa do log, não importa em qual rota aconteceu.
    @app.errorhandler(403)
    def acesso_negado(e):
        registrar("acesso_negado", detalhes=f"{request.method} {request.path}")
        return e

    return app
