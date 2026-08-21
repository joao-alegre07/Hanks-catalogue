from functools import wraps

from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_connection

auth_bp = Blueprint("auth", __name__)


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

    senha_hash = generate_password_hash(senha)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            if cur.fetchone():
                return render_template("cadastro.html", erro="E-mail já cadastrado.")

            cur.execute(
                "INSERT INTO usuarios (nome, email, senha_hash) VALUES (%s, %s, %s)",
                (nome, email, senha_hash),
            )
    finally:
        conn.close()

    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form["email"].strip().lower()
    senha = request.form["senha"]

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, senha_hash FROM usuarios WHERE email = %s", (email,)
            )
            usuario = cur.fetchone()
    finally:
        conn.close()

    if usuario is None or not check_password_hash(usuario["senha_hash"], senha):
        return render_template("login.html", erro="E-mail ou senha inválidos.")

    session.clear()
    session["usuario_id"] = usuario["id"]
    return redirect(url_for("movies.catalogo"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
