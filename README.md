# 🎬 Tom Hanks Catalog

Catálogo web para descobrir e acompanhar a filmografia de Tom Hanks. Busca os filmes ao vivo na API do TMDB e deixa cada usuário favoritar e comentar, com dados isolados por conta.

A aplicação é dividida em dois serviços independentes: o **catálogo** (público) e um **microsserviço de autenticação** (login, papéis de usuário e recuperação de senha), que só é acessível pela rede interna do Docker.

## Funcionalidades

- **Cadastro e login** com senha com hash (nunca em texto puro), isolados num serviço próprio.
- **Catálogo paginado** (20 filmes por página), sempre buscado em tempo real na API do TMDB — pôster, título, sinopse e data de lançamento nunca ficam desatualizados.
- **Favoritos e comentários** por usuário, com isolamento total: o que a conta A favorita ou comenta não aparece pra conta B, mesmo que ela tente adivinhar o ID.
- **Papéis de usuário** (`usuario` / `admin`) geridos pelo serviço de autenticação.
- **Recuperação de senha por e-mail**: link único, expira em 30 minutos e não pode ser reutilizado.

## Arquitetura

```
Navegador ── HTTPS ──> Catálogo (único ponto público)
                           │
                           │ rede interna do Docker
                           ▼
                     Serviço de autenticação (sem porta pública)
                           │
                           ▼
                        MariaDB
```

O catálogo é o único serviço com porta publicada. Login, cadastro, papéis e recuperação de senha
passam pelo catálogo, mas são resolvidos internamente pelo serviço de autenticação — que nunca é
alcançável de fora da rede Docker.

## Stack

- **Backend**: Python + Flask (dois serviços separados)
- **Banco de dados**: MariaDB
- **Dados de filmes**: [TMDB API](https://www.themoviedb.org/documentation/api)
- **E-mail**: Mailtrap (dev) / Brevo (produção)
- **Deploy**: Docker, servido via Gunicorn

## Rodando localmente

Pré-requisitos: Docker, uma [chave de API do TMDB](https://developer.themoviedb.org) e uma [conta Mailtrap](https://mailtrap.io) (ambas gratuitas).

```bash
git clone https://github.com/joao-alegre07/Hanks-catalogue.git
cd Hanks-catalogue
cp .env.example .env
# edite o .env com sua chave TMDB e as credenciais SMTP do Mailtrap
docker compose -f docker-compose.dev.yml up --build
```

Acesse `http://localhost:5000`. Esse compose sobe um MariaDB descartável junto, só pra desenvolvimento — nada de produção usa esse banco.

## Estrutura do projeto

```
app/                      # catálogo
  __init__.py             # cria e configura a aplicação Flask
  auth.py                 # login/cadastro/esqueci-senha (chama o serviço auth)
  movies.py               # catálogo paginado, favoritar, comentar
  db.py                   # conexão com o MariaDB
  tmdb.py                 # integração com a API do TMDB
auth-service/             # serviço de autenticação (sem porta pública)
  app.py                  # cadastro, login, papéis, esqueci-senha
  db.py                   # conexão com o MariaDB
  mail.py                 # envio do e-mail de recuperação de senha
templates/                # páginas (login, cadastro, catálogo, esqueci/resetar senha)
static/                   # CSS
init.sql                  # schema do banco (usuarios, reset_tokens, favoritos, comentarios)
Dockerfile                # imagem do catálogo
auth-service/Dockerfile   # imagem do serviço de autenticação
docker-compose.yml        # produção (Portainer) — os dois serviços + rede compartilhada
docker-compose.dev.yml    # desenvolvimento local
```

## Deploy

As duas imagens são buildadas a partir de seus respectivos `Dockerfile`s e publicadas via
`docker-compose.yml`. O serviço de autenticação **não tem porta publicada pro host** — só é
alcançável pelo catálogo, internamente, pela rede Docker (`interna`). Nenhuma credencial fica no
repositório — tudo é injetado como variável de ambiente em tempo de deploy (ver `.env.example`
pra lista completa: chave da TMDB, credenciais do MariaDB e credenciais SMTP).

## Segurança

- Toda chamada à TMDB e ao MariaDB parte do backend — nada de chave ou senha exposta no HTML/JS que chega no navegador.
- Senhas de usuário armazenadas com hash (`werkzeug.security`).
- Links de redefinição de senha expiram em 30 minutos e não podem ser reutilizados (`reset_tokens.usado`).
- `.env` no `.gitignore`; só `.env.example` (sem valores reais) é versionado.

---

Projeto para a aula do professor [@siriani](https://github.com/siriani).
