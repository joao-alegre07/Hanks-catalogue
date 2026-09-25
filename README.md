# 🎬 Tom Hanks Catalog

Catálogo web para descobrir e acompanhar a filmografia de Tom Hanks. Busca os filmes ao vivo na API do TMDB e deixa cada usuário favoritar, comentar e montar um perfil com foto, bio e os filmes favoritos.

A aplicação é dividida em três serviços independentes: o **catálogo** (público), um **microsserviço de autenticação** (login, papéis de usuário e recuperação de senha) e um **microsserviço de logs** (auditoria, guardada num Redis) e um **object storage** ([Garage](https://garagehq.deuxfleurs.fr/), compatível com S3) pras fotos de perfil. Só o catálogo tem porta pública; o resto só é acessível pela rede interna do Docker.

## Funcionalidades

- **Cadastro e login** com senha com hash (nunca em texto puro), isolados num serviço próprio.
- **Catálogo paginado** (20 filmes por página), sempre buscado em tempo real na API do TMDB — pôster, título, sinopse e data de lançamento nunca ficam desatualizados.
- **Favoritos** por conta — cada usuário tem a sua lista, que aparece no perfil dele.
- **Comentários** visíveis pra qualquer usuário logado (como uma seção de reviews do filme), mas só o próprio autor — ou um admin — pode apagar um comentário.
- **Papéis de usuário** (`usuario` / `admin`) geridos pelo serviço de autenticação.
- **Recuperação de senha por e-mail**: link único, expira em 30 minutos e não pode ser reutilizado.
- **Perfil** com foto, bio e filmes favoritados, no estilo de rede social. A foto vai pro object storage; o banco guarda só a chave do arquivo.
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

Catálogo ──> Garage (bucket "fotos-perfil")   MariaDB guarda só a chave do objeto
```

O catálogo é o único serviço com porta publicada. Login, cadastro, papéis e recuperação de senha
passam pelo catálogo, mas são resolvidos internamente pelo serviço de autenticação — que nunca é
alcançável de fora da rede Docker. Catálogo e auth mandam cada evento relevante pro serviço de
logs, que é o único que escreve no Redis.

## Stack

- **Backend**: Python + Flask (dois serviços separados)
- **Banco de dados**: MariaDB
- **Logs de auditoria**: Redis (Streams)
- **Object storage**: Garage (API S3), acessado com `boto3`
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

Acesse `http://localhost:5000`. Esse compose sobe um MariaDB, um Redis e um Garage descartáveis junto, só pra desenvolvimento — nada de produção usa esses bancos.

As chaves do Garage (`S3_ACCESS_KEY`, `S3_SECRET_KEY`, `GARAGE_RPC_SECRET`) são inventadas por você mesmo — o `.env.example` mostra o comando pra gerar cada uma. No primeiro boot o Garage cria o bucket e a chave de acesso com esses valores.

## Estrutura do projeto

```
app/                      # catálogo
  __init__.py             # cria e configura a aplicação Flask
  auth.py                 # login/cadastro/esqueci-senha (chama o serviço auth)
  movies.py               # catálogo paginado, favoritar, comentar, /admin/logs
  perfil.py               # página de perfil, upload da foto, rota /fotos
  storage.py              # envio e URLs assinadas do object storage (S3)
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
garage/                   # imagem do Garage com o garage.toml (sem segredos)
templates/                # páginas (login, cadastro, catálogo, perfil, esqueci/resetar senha, logs)
static/                   # CSS
init.sql                  # schema do banco (usuarios, reset_tokens, favoritos, comentarios, perfis)
Dockerfile                # imagem do catálogo
auth-service/Dockerfile   # imagem do serviço de autenticação
log-service/Dockerfile    # imagem do serviço de logs
docker-compose.yml        # produção (Portainer) — catálogo, auth, logs, Redis e Garage
docker-compose.dev.yml    # desenvolvimento local
```

## Deploy

As três imagens são buildadas a partir de seus respectivos `Dockerfile`s e publicadas via
`docker-compose.yml`, junto com a imagem oficial do Redis e a do Garage (com o `garage.toml` copiado pra
dentro). Os serviços de autenticação e de logs, o Redis e o Garage **não têm porta publicada pro host** — só são alcançáveis internamente, pela rede padrão do
projeto no Docker. Nenhuma credencial fica no
repositório — tudo é injetado como variável de ambiente em tempo de deploy (ver `.env.example`
pra lista completa: chave da TMDB, credenciais do MariaDB, credenciais SMTP e chaves do Garage).

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
| Ver o perfil de qualquer usuário | ✅ | ✅ |
| Editar o próprio perfil | ✅ | ✅ |
| Editar o perfil de outra pessoa | ❌ | ❌ |

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
| `editar_perfil` | catálogo | usuário salva bio e/ou foto |
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

## Perfil e fotos

Cada usuário tem uma página de perfil (`/perfil/<id>`) com nome, foto, bio e os filmes que
favoritou. O nome do autor de cada comentário no catálogo leva pro perfil dele.

### Por que a foto não vai pro banco

A imagem vai pro **Garage**, um object storage compatível com S3 (usado no lugar do MinIO). No
MariaDB, a tabela `perfis` guarda só a bio e a **chave** do objeto — algo como
`perfis/6/3f2a...c1.png`. Cada upload gera uma chave nova (com um UUID) e o objeto antigo é apagado
depois que o banco já aponta pro novo.

O Garage roda como mais um serviço do compose, sem porta publicada. O `--single-node
--default-bucket` faz ele montar o layout de um nó só e criar o bucket e a chave de acesso no
primeiro boot, a partir de `S3_BUCKET`, `S3_ACCESS_KEY` e `S3_SECRET_KEY` — as mesmas variáveis que o
catálogo usa pra se conectar.

### Validação do upload

- **Tipo**: só JPG, PNG ou WebP. O backend confere os primeiros bytes do arquivo (a "assinatura" de
  cada formato), e não a extensão nem o `Content-Type` que o navegador manda, que dá pra forjar à
  vontade. Um `.png` que na verdade é texto é recusado.
- **Tamanho**: no máximo 2 MB por foto. Além disso o Flask corta qualquer requisição acima de 5 MB
  (`MAX_CONTENT_LENGTH`) antes mesmo de chegar na rota.
- **Bio**: até 280 caracteres.

### Exibição: URL pré-assinada

O bucket é **privado**. Na hora de montar a página de perfil, o catálogo gera uma URL pré-assinada
pra foto, válida por 10 minutos. Quem confere a assinatura e a validade é o próprio Garage: link
adulterado ou vencido volta `403`.

Como o Garage não tem porta pública, a URL assinada chega no navegador com o prefixo `/fotos` do
catálogo, e essa rota só repassa a requisição pro Garage exatamente como veio (mesmo caminho, mesma
query string com a assinatura). O catálogo não decide nada ali — só faz a ponte.

**Por que pré-assinada e não bucket público:**

- Com bucket público, qualquer um que descobrir a chave de um objeto consegue baixar o arquivo pra
  sempre, logado ou não. Em troca é mais simples: a URL é fixa, o navegador faz cache à vontade e
  não tem custo de gerar assinatura a cada página.
- Com URL pré-assinada, só quem abriu um perfil estando logado recebe um link, e esse link morre em
  10 minutos. Se alguém copiar o endereço da foto e mandar pra fora, ele para de funcionar logo. O
  preço é que a URL muda a cada carregamento da página (o cache do navegador ajuda menos) e o
  backend precisa gerar a assinatura sempre que monta o perfil.

Como a foto é de uma pessoa e o resto do sistema já exige login, controlar o acesso valeu mais do
que a simplicidade do bucket público.

### Quem pode editar

Qualquer usuário logado vê o perfil de qualquer outro, mas só edita o próprio. A rota
`POST /perfil/<id>/editar` compara o `<id>` da URL com o `usuario_id` guardado na sessão (definida
pelo servidor no login) e responde `403` se forem diferentes — nem admin edita o perfil de outra
pessoa. O id que vem na requisição nunca decide de quem é o perfil salvo; ele só é conferido. Essa
negativa passa pelo mesmo handler de `403` e entra no log como `acesso_negado`.

---

Projeto para a aula do professor [@siriani](https://github.com/siriani).
