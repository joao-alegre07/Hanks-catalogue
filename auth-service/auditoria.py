import os

import requests


def registrar(acao, usuario_id=None, ip="", detalhes=""):
    url = os.environ.get("LOG_SERVICE_URL")
    if not url:
        return

    try:
        requests.post(
            url.rstrip("/") + "/eventos",
            json={
                "usuario_id": usuario_id,
                "acao": acao,
                "ip": ip,
                "servico": "auth",
                "detalhes": detalhes,
            },
            timeout=2,
        )
    except requests.exceptions.RequestException:
        pass
