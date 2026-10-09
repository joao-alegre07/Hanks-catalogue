import hashlib
import hmac
import json
import time

import pytest
import requests

from app import create_app, movies


class RespostaFalsa:
    def __init__(self, status_code, dados):
        self.status_code = status_code
        self._dados = dados

    def json(self):
        return self._dados


@pytest.fixture
def chamadas(monkeypatch):
    # Nenhum teste pode depender do auth-service ou do log-service de verdade:
    # toda chamada HTTP de saída é anotada aqui e respondida com o que o teste pedir.
    feitas = []
    respostas = {}

    def chamada_falsa(url, **kwargs):
        feitas.append(url)
        for final, resposta in respostas.items():
            if url.endswith(final):
                return resposta
        raise requests.exceptions.ConnectionError(url)

    monkeypatch.setattr(requests, "get", chamada_falsa)
    monkeypatch.setattr(requests, "post", chamada_falsa)
    monkeypatch.setattr(requests, "put", chamada_falsa)
    return feitas, respostas


@pytest.fixture
def client(monkeypatch, chamadas):
    monkeypatch.setenv("SECRET_KEY", "teste")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth:5001")
    monkeypatch.setenv("LOG_SERVICE_URL", "http://log:5002")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_teste")
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_pagina_de_login_abre(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"<form" in resp.data


def test_catalogo_sem_login_redireciona_pro_login(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_login_com_senha_errada_mostra_o_erro_do_auth(client, chamadas):
    _, respostas = chamadas
    respostas["/login"] = RespostaFalsa(401, {"erro": "E-mail ou senha inválidos."})

    resp = client.post("/login", data={"email": "a@a.com", "senha": "errada"})

    assert resp.status_code == 200
    assert "E-mail ou senha inválidos." in resp.get_data(as_text=True)
    with client.session_transaction() as s:
        assert "usuario_id" not in s


def test_login_certo_guarda_o_usuario_na_sessao(client, chamadas):
    _, respostas = chamadas
    respostas["/login"] = RespostaFalsa(200, {"usuario_id": 7, "nome": "Maria", "role": "usuario"})

    resp = client.post("/login", data={"email": "maria@exemplo.com", "senha": "certa"})

    assert resp.status_code == 302
    with client.session_transaction() as s:
        assert s["usuario_id"] == 7
        assert s["role"] == "usuario"


def test_editar_perfil_de_outra_pessoa_da_403_e_vai_pro_log(client, chamadas):
    feitas, _ = chamadas
    with client.session_transaction() as s:
        s["usuario_id"] = 1

    resp = client.post("/perfil/2/editar", data={"bio": "invadindo"})

    assert resp.status_code == 403
    assert "http://log:5002/eventos" in feitas


def test_swagger_do_catalogo_responde(client):
    resp = client.get("/apispec_1.json")
    assert resp.status_code == 200
    assert "/login" in resp.get_json()["paths"]


class ConexaoFalsa:
    """Só o que a rota de favoritar usa do pymysql. Cada fetchone devolve o
    próximo item da fila."""

    def __init__(self, resultados):
        self.resultados = list(resultados)
        self.consultas = []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.consultas.append(sql)

    def fetchone(self):
        return self.resultados.pop(0) if self.resultados else None

    def close(self):
        pass


def favoritar_com(monkeypatch, client, ja_tem, premium, chamadas):
    _, respostas = chamadas
    respostas["/usuarios/1"] = RespostaFalsa(200, {"id": 1, "role": "usuario", "premium": premium})
    banco = ConexaoFalsa([None, {"total": ja_tem}])
    monkeypatch.setattr(movies, "get_connection", lambda: banco)
    with client.session_transaction() as s:
        s["usuario_id"] = 1

    resp = client.post("/favoritar", data={"tmdb_movie_id": "13", "titulo": "Forrest Gump"})
    inseriu = any(sql.startswith("INSERT INTO favoritos") for sql in banco.consultas)
    return resp, inseriu


def test_plano_gratuito_nao_passa_do_limite_de_favoritos(client, monkeypatch, chamadas):
    resp, inseriu = favoritar_com(
        monkeypatch, client, movies.LIMITE_FAVORITOS_GRATIS, False, chamadas
    )
    assert resp.status_code == 403
    assert not inseriu
    assert "http://log:5002/eventos" in chamadas[0]


def test_premium_favorita_alem_do_limite(client, monkeypatch, chamadas):
    resp, inseriu = favoritar_com(
        monkeypatch, client, movies.LIMITE_FAVORITOS_GRATIS, True, chamadas
    )
    assert resp.status_code == 302
    assert inseriu


def assinatura_stripe(corpo, segredo, t=None):
    t = t or int(time.time())
    v1 = hmac.new(segredo.encode(), f"{t}.{corpo}".encode(), hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"


EVENTO_PAGO = json.dumps(
    {
        "id": "evt_teste",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "client_reference_id": "7",
                "payment_status": "paid",
                "customer": "cus_teste",
                "subscription": "sub_teste",
            }
        },
    }
)


def test_webhook_sem_assinatura_e_recusado(client, chamadas):
    feitas, _ = chamadas
    resp = client.post("/stripe/webhook", data=EVENTO_PAGO, content_type="application/json")
    assert resp.status_code == 400
    assert not any(url.endswith("/plano") for url in feitas)


def test_webhook_assinado_com_outro_segredo_e_recusado(client, chamadas):
    feitas, _ = chamadas
    resp = client.post(
        "/stripe/webhook",
        data=EVENTO_PAGO,
        content_type="application/json",
        headers={"Stripe-Signature": assinatura_stripe(EVENTO_PAGO, "whsec_outro")},
    )
    assert resp.status_code == 400
    assert not any(url.endswith("/plano") for url in feitas)


def test_webhook_antigo_reenviado_e_recusado(client, chamadas):
    feitas, _ = chamadas
    uma_hora_atras = int(time.time()) - 3600
    resp = client.post(
        "/stripe/webhook",
        data=EVENTO_PAGO,
        content_type="application/json",
        headers={"Stripe-Signature": assinatura_stripe(EVENTO_PAGO, "whsec_teste", uma_hora_atras)},
    )
    assert resp.status_code == 400
    assert not any(url.endswith("/plano") for url in feitas)


def test_webhook_de_pagamento_liga_o_premium(client, chamadas):
    feitas, respostas = chamadas
    respostas["/usuarios/7/plano"] = RespostaFalsa(200, {"ok": True})

    resp = client.post(
        "/stripe/webhook",
        data=EVENTO_PAGO,
        content_type="application/json",
        headers={"Stripe-Signature": assinatura_stripe(EVENTO_PAGO, "whsec_teste")},
    )

    assert resp.status_code == 200
    assert "http://auth:5001/usuarios/7/plano" in feitas


def test_webhook_com_auth_fora_do_ar_pede_pro_stripe_tentar_de_novo(client, chamadas):
    resp = client.post(
        "/stripe/webhook",
        data=EVENTO_PAGO,
        content_type="application/json",
        headers={"Stripe-Signature": assinatura_stripe(EVENTO_PAGO, "whsec_teste")},
    )
    assert resp.status_code == 503
