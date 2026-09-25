import os

from flask import Flask, request

from .auditoria import registrar


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = os.environ["SECRET_KEY"]
    # Teto do corpo da requisição inteira; o limite da foto em si (2 MB) é
    # conferido na rota de editar perfil.
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    from .auth import auth_bp
    from .movies import movies_bp
    from .perfil import perfil_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(movies_bp)
    app.register_blueprint(perfil_bp)

    # Todo 403 do catálogo passa por aqui, então nenhuma tentativa negada
    # escapa do log, não importa em qual rota aconteceu.
    @app.errorhandler(403)
    def acesso_negado(e):
        registrar("acesso_negado", detalhes=f"{request.method} {request.path}")
        return e

    return app
