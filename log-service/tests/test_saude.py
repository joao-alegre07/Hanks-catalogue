import fakeredis
import pytest

import app as log


@pytest.fixture
def servidor():
    return fakeredis.FakeServer()


@pytest.fixture
def client(monkeypatch, servidor):
    monkeypatch.setattr(log, "r", fakeredis.FakeRedis(server=servidor, decode_responses=True))
    log.app.config["TESTING"] = True
    return log.app.test_client()


def test_health_200_com_o_redis_no_ar(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["dependencias"] == {"redis": "ok"}


def test_health_503_com_o_redis_fora(client, servidor):
    servidor.connected = False

    resp = client.get("/health")

    assert resp.status_code == 503
    assert resp.get_json()["dependencias"] == {"redis": "falhou: ConnectionError"}


def test_liveness_continua_200_com_o_redis_fora(client, servidor):
    servidor.connected = False
    assert client.get("/health/live").status_code == 200


def test_metrics_conta_por_rota_e_status(client):
    client.post("/eventos", json={"acao": "login"})
    client.post("/eventos", json={})
    client.get("/health")

    metricas = client.get("/metrics").get_data(as_text=True)

    assert 'flask_http_request_duration_seconds_count{method="POST",status="201",url_rule="/eventos"}' in metricas
    assert 'flask_http_request_duration_seconds_count{method="POST",status="400",url_rule="/eventos"}' in metricas
    assert 'url_rule="/health"' not in metricas
