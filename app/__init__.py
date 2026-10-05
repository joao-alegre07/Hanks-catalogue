import os

from flasgger import Swagger
from flask import Flask, request
from prometheus_flask_exporter import PrometheusMetrics

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
    from .saude import saude_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(movies_bp)
    app.register_blueprint(perfil_bp)
    app.register_blueprint(saude_bp)

    # /metrics no formato do Prometheus. Agrupa pela regra da rota
    # (/perfil/<int:usuario_id>) e não pelo caminho real, senão cada id vira
    # uma série nova. O /health fica de fora pra o healthcheck do Docker não
    # inflar a contagem de requisições.
    PrometheusMetrics(app, group_by="url_rule", excluded_paths=["^/health"])

    # As rotas do catálogo misturam página (GET) e formulário (POST) na mesma
    # função, então a spec fica num arquivo só em vez de docstring por rota.
    app.config["SWAGGER"] = {"title": "Tom Hanks Catalog", "openapi": "3.0.3"}
    Swagger(app, template_file=os.path.join(os.path.dirname(__file__), "openapi.yml"))

    # Todo 403 do catálogo passa por aqui, então nenhuma tentativa negada
    # escapa do log, não importa em qual rota aconteceu.
    @app.errorhandler(403)
    def acesso_negado(e):
        registrar("acesso_negado", detalhes=f"{request.method} {request.path}")
        return e

    return app
