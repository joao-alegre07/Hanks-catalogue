import os
import uuid

import requests
from botocore.exceptions import BotoCoreError, ClientError
from flask import Blueprint, Response, abort, redirect, render_template, request, session, url_for

from . import storage
from .auditoria import registrar
from .auth import login_required
from .db import get_connection
from .tmdb import TMDB_IMAGE_BASE_URL

perfil_bp = Blueprint("perfil", __name__)

FOTO_TAMANHO_MAX = 2 * 1024 * 1024
BIO_TAMANHO_MAX = 280


def _tipo_da_imagem(dados):
    """Olha os primeiros bytes do arquivo em vez de confiar na extensão ou no
    Content-Type que o navegador mandou, que o cliente controla."""
    if dados.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if dados.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def _buscar_usuario(usuario_id):
    try:
        resp = requests.get(
            os.environ["AUTH_SERVICE_URL"].rstrip("/") + f"/usuarios/{usuario_id}",
            timeout=5,
        )
    except requests.exceptions.RequestException:
        abort(503)

    if resp.status_code == 404:
        abort(404)
    if resp.status_code != 200:
        abort(503)
    return resp.json()


def _buscar_perfil(usuario_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT bio, foto_key FROM perfis WHERE usuario_id = %s", (usuario_id,)
            )
            perfil = cur.fetchone() or {"bio": "", "foto_key": None}

            cur.execute(
                "SELECT tmdb_movie_id, titulo, poster_path FROM favoritos "
                "WHERE usuario_id = %s ORDER BY criado_em DESC",
                (usuario_id,),
            )
            favoritos = cur.fetchall()
    finally:
        conn.close()

    for f in favoritos:
        f["poster_url"] = TMDB_IMAGE_BASE_URL + f["poster_path"] if f["poster_path"] else None

    return perfil, favoritos


def _mostrar_perfil(usuario_id, erro=None, status=200):
    usuario = _buscar_usuario(usuario_id)
    perfil, favoritos = _buscar_perfil(usuario_id)

    foto_url = None
    if perfil["foto_key"]:
        foto_url = storage.url_temporaria(perfil["foto_key"])

    return (
        render_template(
            "perfil.html",
            usuario=usuario,
            bio=perfil["bio"] or "",
            foto_url=foto_url,
            favoritos=favoritos,
            proprio=usuario_id == session["usuario_id"],
            erro=erro,
            bio_max=BIO_TAMANHO_MAX,
            foto_max_mb=FOTO_TAMANHO_MAX // (1024 * 1024),
        ),
        status,
    )


@perfil_bp.route("/perfil")
@login_required
def meu_perfil():
    return redirect(url_for("perfil.ver", usuario_id=session["usuario_id"]))


@perfil_bp.route("/perfil/<int:usuario_id>")
@login_required
def ver(usuario_id):
    return _mostrar_perfil(usuario_id)


@perfil_bp.route("/perfil/<int:usuario_id>/editar", methods=["POST"])
@login_required
def editar(usuario_id):
    # Quem está editando é sempre quem está logado. O id da URL só serve pra
    # conferir -- se não bater com a sessão, a requisição para aqui.
    if usuario_id != session["usuario_id"]:
        abort(403)

    bio = request.form.get("bio", "").strip()
    if len(bio) > BIO_TAMANHO_MAX:
        return _mostrar_perfil(
            usuario_id, erro=f"A bio pode ter no máximo {BIO_TAMANHO_MAX} caracteres.", status=400
        )

    nova_chave = None
    arquivo = request.files.get("foto")
    if arquivo and arquivo.filename:
        dados = arquivo.read(FOTO_TAMANHO_MAX + 1)
        if len(dados) > FOTO_TAMANHO_MAX:
            return _mostrar_perfil(
                usuario_id,
                erro=f"A foto pode ter no máximo {FOTO_TAMANHO_MAX // (1024 * 1024)} MB.",
                status=400,
            )

        tipo = _tipo_da_imagem(dados)
        if tipo is None:
            return _mostrar_perfil(
                usuario_id, erro="Envie uma imagem JPG, PNG ou WebP.", status=400
            )

        extensao, content_type = tipo
        nova_chave = f"perfis/{usuario_id}/{uuid.uuid4().hex}.{extensao}"
        try:
            storage.enviar(nova_chave, dados, content_type)
        except (BotoCoreError, ClientError):
            return _mostrar_perfil(
                usuario_id, erro="Não foi possível salvar a foto. Tente de novo.", status=503
            )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT foto_key FROM perfis WHERE usuario_id = %s", (usuario_id,))
            atual = cur.fetchone()
            chave_antiga = atual["foto_key"] if atual else None

            cur.execute(
                "INSERT INTO perfis (usuario_id, bio, foto_key) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE bio = VALUES(bio), "
                "foto_key = COALESCE(VALUES(foto_key), foto_key)",
                (usuario_id, bio, nova_chave),
            )
    finally:
        conn.close()

    if nova_chave and chave_antiga:
        try:
            storage.apagar(chave_antiga)
        except (BotoCoreError, ClientError):
            pass

    registrar("editar_perfil", detalhes="bio e foto" if nova_chave else "bio")

    return redirect(url_for("perfil.ver", usuario_id=usuario_id))


@perfil_bp.app_errorhandler(413)
def arquivo_grande_demais(e):
    if "usuario_id" not in session:
        return e
    return _mostrar_perfil(
        session["usuario_id"],
        erro=f"A foto pode ter no máximo {FOTO_TAMANHO_MAX // (1024 * 1024)} MB.",
        status=413,
    )


@perfil_bp.route("/fotos/<path:caminho>")
def foto(caminho):
    # Só repassa a URL assinada pro Garage. Quem confere a assinatura e se ela
    # já expirou é o próprio Garage; sem assinatura válida ele responde 403.
    try:
        resp = requests.get(
            storage.url_interna(caminho, request.query_string.decode()),
            timeout=10,
        )
    except requests.exceptions.RequestException:
        abort(503)

    if resp.status_code != 200:
        abort(404 if resp.status_code == 404 else 403)

    return Response(
        resp.content,
        content_type=resp.headers.get("Content-Type", "application/octet-stream"),
        headers={"Cache-Control": f"private, max-age={storage.URL_VALIDADE_SEGUNDOS}"},
    )
