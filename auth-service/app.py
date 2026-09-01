import os
import secrets
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_connection
from mail import enviar_email_reset

app = Flask(__name__)

TOKEN_VALIDADE_MINUTOS = 30


@app.route("/cadastro", methods=["POST"])
def cadastro():
    dados = request.get_json(force=True, silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    if not nome or not email or not senha:
        return jsonify(erro="Preencha todos os campos."), 400

    senha_hash = generate_password_hash(senha)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            if cur.fetchone():
                return jsonify(erro="E-mail já cadastrado."), 409

            cur.execute(
                "INSERT INTO usuarios (nome, email, senha_hash, role) "
                "VALUES (%s, %s, %s, 'usuario')",
                (nome, email, senha_hash),
            )
            usuario_id = cur.lastrowid
    finally:
        conn.close()

    return jsonify(id=usuario_id), 201


@app.route("/login", methods=["POST"])
def login():
    dados = request.get_json(force=True, silent=True) or {}
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, senha_hash, role FROM usuarios WHERE email = %s",
                (email,),
            )
            usuario = cur.fetchone()
    finally:
        conn.close()

    if usuario is None or not check_password_hash(usuario["senha_hash"], senha):
        return jsonify(erro="E-mail ou senha inválidos."), 401

    return jsonify(usuario_id=usuario["id"], nome=usuario["nome"], role=usuario["role"])


@app.route("/usuarios/<int:usuario_id>", methods=["GET"])
def obter_usuario(usuario_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, email, role FROM usuarios WHERE id = %s",
                (usuario_id,),
            )
            usuario = cur.fetchone()
    finally:
        conn.close()

    if usuario is None:
        return jsonify(erro="Usuário não encontrado."), 404

    return jsonify(usuario)


@app.route("/esqueci-senha", methods=["POST"])
def esqueci_senha():
    dados = request.get_json(force=True, silent=True) or {}
    email = (dados.get("email") or "").strip().lower()
    base_url = (dados.get("base_url") or "").rstrip("/")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            usuario = cur.fetchone()

            if usuario is not None:
                token = secrets.token_urlsafe(32)
                expira_em = datetime.utcnow() + timedelta(minutes=TOKEN_VALIDADE_MINUTOS)
                cur.execute(
                    "INSERT INTO reset_tokens (token, usuario_id, expira_em) "
                    "VALUES (%s, %s, %s)",
                    (token, usuario["id"], expira_em),
                )
    finally:
        conn.close()

    # Sempre responde OK, exista ou não o e-mail — evita confirmar pra quem
    # está tentando adivinhar contas cadastradas se um e-mail existe ou não.
    if usuario is not None:
        link = f"{base_url}/resetar-senha?token={token}"
        enviar_email_reset(email, link)

    return jsonify(ok=True)


@app.route("/resetar-senha", methods=["POST"])
def resetar_senha():
    dados = request.get_json(force=True, silent=True) or {}
    token = dados.get("token") or ""
    nova_senha = dados.get("nova_senha") or ""

    if not token or not nova_senha:
        return jsonify(erro="Dados incompletos."), 400

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT usuario_id, expira_em, usado FROM reset_tokens WHERE token = %s",
                (token,),
            )
            registro = cur.fetchone()

            if registro is None:
                return jsonify(erro="Link inválido."), 400
            if registro["usado"]:
                return jsonify(erro="Esse link já foi usado."), 400
            if registro["expira_em"] < datetime.utcnow():
                return jsonify(erro="Esse link expirou. Peça um novo."), 400

            senha_hash = generate_password_hash(nova_senha)
            cur.execute(
                "UPDATE usuarios SET senha_hash = %s WHERE id = %s",
                (senha_hash, registro["usuario_id"]),
            )
            cur.execute(
                "UPDATE reset_tokens SET usado = TRUE WHERE token = %s", (token,)
            )
    finally:
        conn.close()

    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
