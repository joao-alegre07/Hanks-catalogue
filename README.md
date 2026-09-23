# 🎬 Tom Hanks Catalog

Catálogo web para descobrir e acompanhar a filmografia de Tom Hanks. Busca os filmes ao vivo na API do TMDB e deixa cada usuário favoritar e comentar, com dados isolados por conta.

A aplicação é dividida em três serviços independentes: o **catálogo** (público), um **microsserviço de autenticação** (login, papéis de usuário e recuperação de senha) e um **microsserviço de logs** (auditoria, guardada num Redis). Os dois últimos só são acessíveis pela rede interna do Docker.

## Funcionalidades

- **Cadastro e login** com senha com hash (nunca em texto puro), isolados num serviço próprio.
- **Catálogo paginado** (20 filmes por página), sempre buscado em tempo real na API do TMDB — pôster, título, sinopse e data de lançamento nunca ficam desatualizados.
- **Favoritos** privados por conta — o que a conta A favorita não aparece pra conta B.
- **Comentários** visíveis pra qualquer usuário logado (como uma seção de reviews do filme), mas só o próprio autor — ou um admin — pode apagar um comentário.
- **Papéis de usuário** (`usuario` / `admin`) geridos pelo serviço de autenticação.
- **Recuperação de senha por e-mail**: link único, expira em 30 minutos e não pode ser reutilizado.
- **Log de auditoria**: login, logout, favoritos, comentários, moderação e toda tentativa negada por permissão ficam registrados — só admin consulta.

## Arquitetura

```
Navegador ── HTTPS ──> Catálogo (único ponto público)
                        │      │
                        │      │ rede interna do Docker
                        │      ▼
                        │   Serviço de autenticação ──> MariaDB
                        │      │
                        ▼      ▼
                     Serviço de logs (eventos)
                           │
                           ▼
                     Redis (Stream "auditoria")
```

O catálogo é o único serviço com porta publicada. Login, cadastro, papéis e recuperação de senha
passam pelo catálogo, mas são resolvidos internamente pelo serviço de autenticação — que nunca é
alcançável de fora da rede Docker. Catálogo e auth mandam cada evento relevante pro serviço de
logs, que é o único que escreve no Redis.

## Stack

- **Backend**: Python + Flask (dois serviços separados)
- **Banco de dados**: MariaDB
- **Logs de auditoria**: Redis (Streams)
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

Acesse `http://localhost:5000`. Esse compose sobe um MariaDB e um Redis descartáveis junto, só pra desenvolvimento — nada de produção usa esses bancos.

## Estrutura do projeto

```
app/                      # catálogo
  __init__.py             # cria e configura a aplicação Flask
  auth.py                 # login/cadastro/esqueci-senha (chama o serviço auth)
  movies.py               # catálogo paginado, favoritar, comentar, /admin/logs
  auditoria.py            # envia eventos pro serviço de logs
  db.py                   # conexão com o MariaDB
  tmdb.py                 # integração com a API do TMDB
auth-service/             # serviço de autenticação (sem porta pública)
  app.py                  # cadastro, login, papéis, esqueci-senha
  db.py                   # conexão com o MariaDB
  mail.py                 # envio do e-mail de recuperação de senha
  auditoria.py            # envia eventos de login pro serviço de logs
log-service/              # serviço de logs (sem porta pública)
  app.py                  # grava (XADD) e lista (XREVRANGE) eventos no Redis
templates/                # páginas (login, cadastro, catálogo, esqueci/resetar senha, logs)
static/                   # CSS
init.sql                  # schema do banco (usuarios, reset_tokens, favoritos, comentarios)
Dockerfile                # imagem do catálogo
auth-service/Dockerfile   # imagem do serviço de autenticação
log-service/Dockerfile    # imagem do serviço de logs
docker-compose.yml        # produção (Portainer) — catálogo, auth, logs e Redis
docker-compose.dev.yml    # desenvolvimento local
```

## Deploy

As três imagens são buildadas a partir de seus respectivos `Dockerfile`s e publicadas via
`docker-compose.yml`, junto com a imagem oficial do Redis. Os serviços de autenticação e de logs e o
Redis **não têm porta publicada pro host** — só são alcançáveis internamente, pela rede padrão do
projeto no Docker. Nenhuma credencial fica no
repositório — tudo é injetado como variável de ambiente em tempo de deploy (ver `.env.example`
pra lista completa: chave da TMDB, credenciais do MariaDB e credenciais SMTP).

## Segurança

- Toda chamada à TMDB e ao MariaDB parte do backend — nada de chave ou senha exposta no HTML/JS que chega no navegador.
- Senhas de usuário armazenadas com hash (`werkzeug.security`).
- Links de redefinição de senha expiram em 30 minutos e não podem ser reutilizados (`reset_tokens.usado`).
- `.env` no `.gitignore`; só `.env.example` (sem valores reais) é versionado.

## Permissões por papel

| Ação | `usuario` | `admin` |
|---|---|---|
| Ver catálogo, favoritar, comentar | ✅ | ✅ |
| Apagar o próprio comentário | ✅ | ✅ |
| Apagar comentário de qualquer usuário (moderação) | ❌ | ✅ |
| Consultar o log de auditoria (`/admin/logs`) | ❌ | ✅ |

A checagem acontece sempre no backend, nunca só escondendo um botão na tela: chamar o endpoint
`POST /comentarios/<id>/deletar` direto (por curl, Postman etc.) tentando apagar o comentário de
outra pessoa retorna `403` pra quem não é admin, independente do que a interface mostra.

## Padrão A ou B?

O `auth-service` hoje segue o **Padrão A (enforcement centralizado)**: antes de deixar alguém
apagar o comentário de outra pessoa, o catálogo faz uma chamada HTTP pro `auth-service`
(`GET /usuarios/<id>`) perguntando o papel *atual* daquele usuário — não confia em nada guardado
na sessão desde o login.

Se fosse pro Padrão B (claims num JWT assinado no login), o catálogo decodificaria o papel
localmente e decidiria sozinho, sem chamada de rede extra a cada tentativa de apagar um
comentário — mais rápido, mas com uma troca: se o papel de alguém mudasse (um admin virando
usuário comum, por exemplo), isso só teria efeito depois que o token expirasse e fosse renovado,
em vez de valer na hora, como acontece hoje.

## Log de auditoria

Cada ação relevante gera um evento que é enviado por HTTP pro `log-service`. Nenhum outro serviço
escreve direto no Redis — assim o log fica centralizado num lugar só, separado do código do catálogo.

| Ação | Quem registra | Quando |
|---|---|---|
| `login` / `login_falhou` | auth | tentativa de login (com e sem sucesso) |
| `logout` | catálogo | usuário sai |
| `favoritar` / `desfavoritar` | catálogo | clique no botão de favorito |
| `comentar` | catálogo | novo comentário |
| `apagar_comentario` | catálogo | autor apaga o próprio comentário |
| `moderar_comentario` | catálogo | admin apaga o comentário de outra pessoa |
| `acesso_negado` | catálogo | qualquer resposta `403` (rota e método ficam nos detalhes) |

Cada evento tem `usuario_id`, `acao` e `timestamp` (UTC, definido pelo `log-service` na hora em que
recebe o evento, pra que todos os serviços fiquem na mesma linha do tempo), além do `ip` de origem,
do `servico` que mandou e de um campo livre de `detalhes`.

O `acesso_negado` é registrado num handler de erro `403` do Flask, e não rota por rota — assim
qualquer tentativa barrada entra no log, inclusive em rotas que forem criadas depois.

### Por que Redis Streams

Os eventos ficam num Redis Stream (`XADD auditoria * ...`). O Stream já gera um ID por evento a
partir do horário do servidor, então a ordem cronológica vem de graça, e a consulta dos últimos N
eventos é um único `XREVRANGE auditoria + - COUNT N`. O Redis roda com `appendonly yes` e um volume
próprio, então os eventos sobrevivem a um restart do container.

Se o `log-service` estiver fora do ar, as ações do usuário continuam funcionando normalmente — o
envio do evento tem timeout curto e a falha é ignorada.

### Consulta

`GET /admin/logs` (link "Logs" no topo do catálogo, visível só pra admin) lista os últimos 50
eventos, do mais recente pro mais antigo; `?n=` muda a quantidade (até 500). A rota usa o mesmo
controle de acesso do resto do sistema: o catálogo pergunta o papel atual do usuário pro
`auth-service` e devolve `403` pra quem não é admin — e essa própria tentativa também vai pro log.

---

Projeto para a aula do professor [@siriani](https://github.com/siriani).
