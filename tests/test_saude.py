import pymysql
import pytest

from app import create_app, saude


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "teste")
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def ok():
    pass


def fora_do_ar():
    raise pymysql.err.OperationalError(2003, "Can't connect")


def test_health_200_com_tudo_no_ar(client, monkeypatch):
    monkeypatch.setattr(saude, "DEPENDENCIAS", {"mariadb": ok, "garage": ok})

    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.get_json()["dependencias"] == {"mariadb": "ok", "garage": "ok"}


def test_health_503_com_o_banco_fora(client, monkeypatch):
    monkeypatch.setattr(saude, "DEPENDENCIAS", {"mariadb": fora_do_ar, "garage": ok})

    resp = client.get("/health")

    assert resp.status_code == 503
    dados = resp.get_json()
    assert dados["status"] == "falhou"
    assert dados["dependencias"]["mariadb"] == "falhou: OperationalError"
    assert dados["dependencias"]["garage"] == "ok"


def test_liveness_nao_depende_de_nada(client, monkeypatch):
    monkeypatch.setattr(saude, "DEPENDENCIAS", {"mariadb": fora_do_ar, "garage": fora_do_ar})
    assert client.get("/health/live").status_code == 200


def test_metrics_no_formato_do_prometheus(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"flask_http_request_duration_seconds" in resp.data
