import os

import requests

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

ATOR_BUSCADO = "Tom Hanks"


def _api_key():
    return os.environ["TMDB_API_KEY"]


def buscar_person_id(nome=ATOR_BUSCADO):
    resp = requests.get(
        f"{TMDB_BASE_URL}/search/person",
        params={"api_key": _api_key(), "query": nome},
        timeout=10,
    )
    resp.raise_for_status()
    resultados = resp.json().get("results", [])
    if not resultados:
        return None
    return resultados[0]["id"]


def buscar_filmes(person_id):
    resp = requests.get(
        f"{TMDB_BASE_URL}/person/{person_id}/movie_credits",
        params={"api_key": _api_key()},
        timeout=10,
    )
    resp.raise_for_status()
    elenco = resp.json().get("cast", [])

    filmes = [f for f in elenco if f.get("poster_path")]
    filmes.sort(key=lambda f: f.get("release_date") or "", reverse=True)

    for filme in filmes:
        filme["poster_url"] = TMDB_IMAGE_BASE_URL + filme["poster_path"]

    return filmes


def buscar_filmes_tom_hanks():
    person_id = buscar_person_id()
    if person_id is None:
        return []
    return buscar_filmes(person_id)
