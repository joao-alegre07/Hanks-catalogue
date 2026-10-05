import pytest
import requests

from app import create_app


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

    def post_falso(url, **kwargs):
        feitas.append(url)
        for final, resposta in respostas.items():
            if url.endswith(final):
                return resposta
        raise requests.exceptions.ConnectionError(url)

    monkeypatch.setattr(requests, "post", post_falso)
    return feitas, respostas


@pytest.fixture
def client(monkeypatch, chamadas):
    monkeypatch.setenv("SECRET_KEY", "teste")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth:5001")
    monkeypatch.setenv("LOG_SERVICE_URL", "http://log:5002")
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
