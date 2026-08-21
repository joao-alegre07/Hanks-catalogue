import math

from flask import Blueprint, redirect, render_template, request, session, url_for

from .auth import login_required
from .db import get_connection
from .tmdb import buscar_filmes_tom_hanks

movies_bp = Blueprint("movies", __name__)

FILMES_POR_PAGINA = 20


@movies_bp.route("/")
@login_required
def catalogo():
    usuario_id = session["usuario_id"]
    filmes = buscar_filmes_tom_hanks()

    total_paginas = max(1, math.ceil(len(filmes) / FILMES_POR_PAGINA))
    pagina = request.args.get("page", 1, type=int)
    pagina = min(max(pagina, 1), total_paginas)

    inicio = (pagina - 1) * FILMES_POR_PAGINA
    filmes_pagina = filmes[inicio : inicio + FILMES_POR_PAGINA]

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tmdb_movie_id FROM favoritos WHERE usuario_id = %s",
                (usuario_id,),
            )
            favoritados = {row["tmdb_movie_id"] for row in cur.fetchall()}

            cur.execute(
                "SELECT tmdb_movie_id, texto, criado_em FROM comentarios "
                "WHERE usuario_id = %s ORDER BY criado_em DESC",
                (usuario_id,),
            )
            comentarios_por_filme = {}
            for row in cur.fetchall():
                comentarios_por_filme.setdefault(row["tmdb_movie_id"], []).append(row)
    finally:
        conn.close()

    for filme in filmes_pagina:
        filme["favoritado"] = filme["id"] in favoritados
        filme["comentarios"] = comentarios_por_filme.get(filme["id"], [])

    return render_template(
        "catalogo.html",
        filmes=filmes_pagina,
        pagina=pagina,
        total_paginas=total_paginas,
    )


@movies_bp.route("/favoritar", methods=["POST"])
@login_required
def favoritar():
    usuario_id = session["usuario_id"]
    tmdb_movie_id = int(request.form["tmdb_movie_id"])
    titulo = request.form["titulo"]
    poster_path = request.form.get("poster_path")
    pagina = request.form.get("page", 1, type=int)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM favoritos WHERE usuario_id = %s AND tmdb_movie_id = %s",
                (usuario_id, tmdb_movie_id),
            )
            if cur.fetchone():
                cur.execute(
                    "DELETE FROM favoritos WHERE usuario_id = %s AND tmdb_movie_id = %s",
                    (usuario_id, tmdb_movie_id),
                )
            else:
                cur.execute(
                    "INSERT INTO favoritos (usuario_id, tmdb_movie_id, titulo, poster_path) "
                    "VALUES (%s, %s, %s, %s)",
                    (usuario_id, tmdb_movie_id, titulo, poster_path),
                )
    finally:
        conn.close()

    return redirect(url_for("movies.catalogo", page=pagina))


@movies_bp.route("/comentar", methods=["POST"])
@login_required
def comentar():
    usuario_id = session["usuario_id"]
    tmdb_movie_id = int(request.form["tmdb_movie_id"])
    texto = request.form["texto"].strip()
    pagina = request.form.get("page", 1, type=int)

    if texto:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO comentarios (usuario_id, tmdb_movie_id, texto) "
                    "VALUES (%s, %s, %s)",
                    (usuario_id, tmdb_movie_id, texto),
                )
        finally:
            conn.close()

    return redirect(url_for("movies.catalogo", page=pagina))
