import os
from datetime import datetime, timezone

import redis
from flask import Flask, jsonify, request

app = Flask(__name__)

STREAM = "auditoria"

r = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)


@app.route("/eventos", methods=["POST"])
def registrar():
    dados = request.get_json(force=True, silent=True) or {}
    acao = (dados.get("acao") or "").strip()
    if not acao:
        return jsonify(erro="Campo 'acao' é obrigatório."), 400

    # O horário é sempre o do log-service, não o de quem mandou o evento --
    # assim todos os serviços ficam na mesma linha do tempo.
    evento = {
        "usuario_id": dados.get("usuario_id") or "",
        "acao": acao,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ip": dados.get("ip") or "",
        "servico": dados.get("servico") or "",
        "detalhes": dados.get("detalhes") or "",
    }
    evento_id = r.xadd(STREAM, {k: str(v) for k, v in evento.items()})
    return jsonify(id=evento_id), 201


@app.route("/eventos", methods=["GET"])
def listar():
    n = min(max(request.args.get("n", 50, type=int), 1), 500)
    eventos = [{"id": evento_id, **campos} for evento_id, campos in r.xrevrange(STREAM, count=n)]
    return jsonify(eventos)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5002)))
