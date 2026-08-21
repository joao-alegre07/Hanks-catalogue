# Catálogo de Filmes — Tom Hanks

Atividade da disciplina Introdução à Computação em Nuvem (ISW055).

Aplicação Flask que busca os filmes com Tom Hanks na API do TMDB e permite que cada usuário cadastrado favorite e comente filmes, com os dados isolados por conta (persistidos em MariaDB).

## Funcionalidades

- Cadastro e login próprios da aplicação (sem relação com as credenciais de MySQL/Portainer).
- Catálogo paginado (20 filmes por página) com pôster, título, sinopse e data de lançamento, sempre buscado ao vivo na API do TMDB.
- Favoritar e comentar filmes, com os dados isolados por usuário — o que a conta A favorita/comenta não aparece pra conta B.

## Arquitetura

- **Backend**: Flask (Python), sessão de login própria da aplicação.
- **Dados dos filmes**: sempre buscados ao vivo na API do TMDB (nunca armazenados no banco).
- **Persistência**: MariaDB — apenas `usuarios`, `favoritos` e `comentarios` (ver [`init.sql`](init.sql)).
- **Segregação**: toda consulta a favoritos/comentários é filtrada por `usuario_id` da sessão logada.
- **Credenciais**: só existem como variáveis de ambiente no servidor (backend). Nunca aparecem no código nem em JavaScript client-side.

## Rodando localmente

Uso local (banco MariaDB descartável, só pra dev):

```bash
cp .env.example .env
# preencha .env com sua chave TMDB e uma senha qualquer para o banco local
docker compose -f docker-compose.dev.yml up --build
```

Acesse `http://localhost:5000`.

## Deploy no Portainer

O `docker-compose.yml` da raiz (diferente do `docker-compose.dev.yml`) é o usado em produção: um único
serviço `app`, publicado na porta reservada, conectando direto no MariaDB real da disciplina — sem
banco local.

1. Suba este repositório no GitHub (público) — feito.
2. No Portainer: **Stacks → + Add stack → aba Repository**.
3. Cole a URL deste repositório.
4. Em **Environment variables**, adicione (sem isso o app não conecta em nada):
   - `SECRET_KEY`
   - `TMDB_API_KEY`
   - `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
5. Clique em **Deploy the stack** — o Portainer clona o repositório e builda a imagem a partir do `Dockerfile`.
6. A aplicação deve responder em `https://joao-alegre-isw055.lapps.studio` (a porta do host, 8212, é o
   que vincula o container a esse subdomínio).

## Variáveis de ambiente

Ver [`.env.example`](.env.example) para a lista completa. Nenhum valor real é versionado — `.env` está no `.gitignore`.
