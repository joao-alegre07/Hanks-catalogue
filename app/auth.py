import os
from functools import wraps

import requests
from flask import Blueprint, redirect, render_template, request, session, url_for

auth_bp = Blueprint("auth", __name__)


def _auth_url(caminho):
    return os.environ["AUTH_SERVICE_URL"].rstrip("/") + caminho


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "GET":
        return render_template("cadastro.html")

    nome = request.form["nome"].strip()
    email = request.form["email"].strip().lower()
    senha = request.form["senha"]

    if not nome or not email or not senha:
        return render_template("cadastro.html", erro="Preencha todos os campos.")

    try:
        resp = requests.post(
            _auth_url("/cadastro"),
            json={"nome": nome, "email": email, "senha": senha},
            timeout=5,
        )
    except requests.exceptions.RequestException:
        return render_template("cadastro.html", erro="Serviço de login indisponível. Tente de novo.")

    if resp.status_code == 201:
        return redirect(url_for("auth.login"))

    erro = resp.json().get("erro", "Não foi possível cadastrar.")
    return render_template("cadastro.html", erro=erro)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form["email"].strip().lower()
    senha = request.form["senha"]

    try:
        resp = requests.post(
            _auth_url("/login"), json={"email": email, "senha": senha}, timeout=5
        )
    except requests.exceptions.RequestException:
        return render_template("login.html", erro="Serviço de login indisponível. Tente de novo.")

    if resp.status_code != 200:
        erro = resp.json().get("erro", "E-mail ou senha inválidos.")
        return render_template("login.html", erro=erro)

    dados = resp.json()
    session.clear()
    session["usuario_id"] = dados["usuario_id"]
    session["nome"] = dados["nome"]
    session["role"] = dados["role"]
    return redirect(url_for("movies.catalogo"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/esqueci-senha", methods=["GET", "POST"])
def esqueci_senha():
    if request.method == "GET":
        return render_template("esqueci_senha.html")

    email = request.form["email"].strip().lower()
    base_url = os.environ.get("PUBLIC_APP_URL", request.url_root).rstrip("/")

    try:
        requests.post(
            _auth_url("/esqueci-senha"),
            json={"email": email, "base_url": base_url},
            timeout=5,
        )
    except requests.exceptions.RequestException:
        pass

    # Sempre mostra a mesma mensagem, exista ou não o e-mail cadastrado.
    return render_template(
        "esqueci_senha.html",
        mensagem="Se esse e-mail estiver cadastrado, você vai receber um link em instantes.",
    )


@auth_bp.route("/resetar-senha", methods=["GET", "POST"])
def resetar_senha():
    if request.method == "GET":
        token = request.args.get("token", "")
        return render_template("resetar_senha.html", token=token)

    token = request.form["token"]
    nova_senha = request.form["nova_senha"]

    try:
        resp = requests.post(
            _auth_url("/resetar-senha"),
            json={"token": token, "nova_senha": nova_senha},
            timeout=5,
        )
    except requests.exceptions.RequestException:
        return render_template(
            "resetar_senha.html", token=token, erro="Serviço de login indisponível. Tente de novo."
        )

    if resp.status_code != 200:
        erro = resp.json().get("erro", "Não foi possível trocar a senha.")
        return render_template("resetar_senha.html", token=token, erro=erro)

    return redirect(url_for("auth.login", redefinida=1))
