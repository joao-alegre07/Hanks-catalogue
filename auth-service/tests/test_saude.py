import pymysql
import pytest

import app as auth


@pytest.fixture
def client():
    auth.app.config["TESTING"] = True
    return auth.app.test_client()


def test_health_503_com_o_banco_fora(client, monkeypatch):
    def fora_do_ar(**kwargs):
        raise pymysql.err.OperationalError(2003, "Can't connect")

    monkeypatch.setattr(auth, "get_connection", fora_do_ar)

    resp = client.get("/health")

    assert resp.status_code == 503
    assert resp.get_json()["dependencias"] == {"mariadb": "falhou: OperationalError"}


def test_health_200_com_o_banco_no_ar(client, monkeypatch):
    class Conexao:
        def cursor(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql):
            assert sql == "SELECT 1"

        def close(self):
            pass

    monkeypatch.setattr(auth, "get_connection", lambda **kwargs: Conexao())
    assert client.get("/health").status_code == 200
