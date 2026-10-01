import os
import secrets
from datetime import datetime, timedelta

from flasgger import Swagger
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from auditoria import registrar
from db import get_connection
from mail import enviar_email_reset

app = Flask(__name__)
app.config["SWAGGER"] = {"title": "auth-service", "openapi": "3.0.3"}
Swagger(
    app,
    template={
        "info": {
            "title": "auth-service",
            "version": "1.0",
            "description": "Serviço interno de autenticação: cadastro, login, papéis e "
            "recuperação de senha. Sem porta pública: em produção só o catálogo fala com ele, "
            "pela rede do Docker.",
        },
        "components": {
            "schemas": {
                "Erro": {
                    "type": "object",
                    "properties": {"erro": {"type": "string"}},
                },
                "Ok": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean", "example": True}},
                },
            }
        },
    },
)

TOKEN_VALIDADE_MINUTOS = 30


@app.route("/cadastro", methods=["POST"])
def cadastro():
    """Cria uma conta nova (sempre com papel usuario)
    ---
    tags: [contas]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [nome, email, senha]
            properties:
              nome:
                type: string
                example: Maria
              email:
                type: string
                example: maria@exemplo.com
              senha:
                type: string
                example: umasenhaqualquer
    responses:
      201:
        description: Conta criada.
        content:
          application/json:
            example: {"id": 7}
      400:
        description: Algum campo veio vazio.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Erro'
            example: {"erro": "Preencha todos os campos."}
      409:
        description: Já existe conta com esse e-mail.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Erro'
            example: {"erro": "E-mail já cadastrado."}
    """
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
    """Confere e-mail e senha
    ---
    tags: [contas]
    description: Toda tentativa, certa ou errada, vira um evento no log-service.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [email, senha]
            properties:
              email:
                type: string
                example: maria@exemplo.com
              senha:
                type: string
                example: umasenhaqualquer
              ip:
                type: string
                description: IP de quem tentou logar, repassado pelo catálogo pro log.
                example: 177.10.20.30
    responses:
      200:
        description: Login certo.
        content:
          application/json:
            example: {"usuario_id": 7, "nome": "Maria", "role": "usuario"}
      401:
        description: E-mail não cadastrado ou senha errada (mesma resposta nos dois casos).
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Erro'
            example: {"erro": "E-mail ou senha inválidos."}
    """
    dados = request.get_json(force=True, silent=True) or {}
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""
    ip = dados.get("ip") or ""

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
        registrar(
            "login_falhou",
            usuario_id=usuario["id"] if usuario else None,
            ip=ip,
            detalhes=email,
        )
        return jsonify(erro="E-mail ou senha inválidos."), 401

    registrar("login", usuario_id=usuario["id"], ip=ip)
    return jsonify(usuario_id=usuario["id"], nome=usuario["nome"], role=usuario["role"])


@app.route("/usuarios/<int:usuario_id>", methods=["GET"])
def obter_usuario(usuario_id):
    """Dados e papel atual de um usuário
    ---
    tags: [contas]
    description: O catálogo chama essa rota antes de cada ação de admin, pra checar o papel na hora.
    parameters:
      - name: usuario_id
        in: path
        required: true
        schema:
          type: integer
          example: 7
    responses:
      200:
        description: Usuário encontrado.
        content:
          application/json:
            example: {"id": 7, "nome": "Maria", "email": "maria@exemplo.com", "role": "usuario"}
      404:
        description: Não existe usuário com esse id.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Erro'
            example: {"erro": "Usuário não encontrado."}
    """
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
    """Pede um link de redefinição de senha
    ---
    tags: [senha]
    description: >
      Se o e-mail existir, gera um token válido por 30 minutos e manda o link por e-mail.
      A resposta é sempre a mesma, exista ou não a conta.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [email, base_url]
            properties:
              email:
                type: string
                example: maria@exemplo.com
              base_url:
                type: string
                description: Endereço público do catálogo, usado pra montar o link.
                example: https://joao-alegre-isw055.lapps.studio
    responses:
      200:
        description: Pedido recebido.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Ok'
    """
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
    """Troca a senha usando o token do e-mail
    ---
    tags: [senha]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [token, nova_senha]
            properties:
              token:
                type: string
                example: 3q2-7w9Jd0x...
              nova_senha:
                type: string
                example: outrasenha
    responses:
      200:
        description: Senha trocada; o token não serve mais.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Ok'
      400:
        description: Faltou campo, ou o token não existe, já foi usado ou expirou.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Erro'
            examples:
              incompleto:
                value: {"erro": "Dados incompletos."}
              invalido:
                value: {"erro": "Link inválido."}
              usado:
                value: {"erro": "Esse link já foi usado."}
              expirado:
                value: {"erro": "Esse link expirou. Peça um novo."}
    """
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
