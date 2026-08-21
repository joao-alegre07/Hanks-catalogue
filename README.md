# 🎬 Tom Hanks Catalog

Catálogo web para descobrir e acompanhar a filmografia de Tom Hanks. Busca os filmes ao vivo na API do TMDB e deixa cada usuário favoritar e comentar, com dados isolados por conta.

## Funcionalidades

- **Cadastro e login** próprios da aplicação, com senha com hash (nunca em texto puro).
- **Catálogo paginado** (20 filmes por página), sempre buscado em tempo real na API do TMDB — pôster, título, sinopse e data de lançamento nunca ficam desatualizados.
- **Favoritos e comentários** por usuário, com isolamento total: o que a conta A favorita ou comenta não aparece pra conta B, mesmo que ela tente adivinhar o ID.

## Stack

- **Backend**: Python + Flask
- **Banco de dados**: MariaDB
- **Dados de filmes**: [TMDB API](https://www.themoviedb.org/documentation/api)
- **Deploy**: Docker, servido via Gunicorn

## Rodando localmente

Pré-requisitos: Docker e uma [chave de API do TMDB](https://developer.themoviedb.org) (gratuita).

```bash
git clone https://github.com/joao-alegre07/Hanks-catalogue.git
cd Hanks-catalogue
cp .env.example .env
# edite o .env com sua chave TMDB (o resto já tem valores padrão pro banco local)
docker compose -f docker-compose.dev.yml up --build
```

Acesse `http://localhost:5000`. Esse compose sobe um MariaDB descartável junto, só pra desenvolvimento — nada de produção usa esse banco.

## Estrutura do projeto

```
app/
  __init__.py    # cria e configura a aplicação Flask
  auth.py        # cadastro, login, logout, decorator de sessão
  movies.py      # catálogo paginado, favoritar, comentar
  db.py          # conexão com o MariaDB
  tmdb.py        # integração com a API do TMDB
templates/       # páginas (login, cadastro, catálogo)
static/          # CSS
init.sql         # schema do banco (usuarios, favoritos, comentarios)
Dockerfile
docker-compose.yml      # produção (Portainer)
docker-compose.dev.yml  # desenvolvimento local
```

## Deploy

A imagem é buildada a partir do `Dockerfile` e publicada via `docker-compose.yml`. Nenhuma credencial fica no repositório — tudo é injetado como variável de ambiente em tempo de deploy (ver `.env.example` pra lista completa: chave da TMDB e credenciais do MariaDB).

## Segurança

- Toda chamada à TMDB e ao MariaDB parte do backend — nada de chave ou senha exposta no HTML/JS que chega no navegador.
- Senhas de usuário armazenadas com hash (`werkzeug.security`).
- `.env` no `.gitignore`; só `.env.example` (sem valores reais) é versionado.

---

Projeto para a aula do professor [@siriani](https://github.com/siriani).
