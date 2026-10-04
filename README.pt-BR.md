<div align="center">

<img src="assets/banner.svg" alt="devin-pm" width="100%"/>

</div>

# devin-pm

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

Um gestor de projetos sobre as tuas sessões do Devin — lê o `sessions.db`
(e, opcionalmente, o `state.vscdb` da GUI), agrupa o trabalho por
repositório/projeto e gera relatórios de status, milestones e um registo
de projetos em formato legível por máquina.

## O problema

Cada sessão da CLI do Devin fica gravada num `sessions.db` local, mas a
aplicação não te dá uma visão por projeto. Ao fim de algumas semanas a base
de dados tem uma centena de sessões e não consegues responder às perguntas
básicas: *em que repos trabalhei realmente? qual é o estado do projeto X?
que milestones estão em aberto?* O histórico está todo lá — mas preso numa
lista plana de sessões, sem agrupamento, sem rollups, sem nada que possas
entregar num relatório ou a outra ferramenta.

## Trabalho anterior (prior art)

O workspace do orquestrador provou a ideia com um script de auditoria
pontual (`audit_sessions.py` → `sessions_report.md` /
`sessions_summary.csv`): uma auditoria lifetime de 100+ sessões agrupadas
por `working_directory`. Este projeto transforma esse script numa
ferramenta mantida sobre o parser `SessionsStore` do
[`devin-internals-spec`](https://github.com/Icaro0310/devin-internals-spec)
— não reimplementa a leitura da DB nem reinventa o agrupamento.

## O que o torna Devin-native

*É um gestor de projetos sobre as tuas sessões do Devin — lê o
`sessions.db` e dá-te status por repo, milestones e um registo.*

1. **Lado a lado:** o Devin lista sessões mas não consegue agrupá-las por
   repositório, marcar uma como milestone, nem emitir um registo de
   projetos — o `devin-pm` faz o que a base não consegue de todo.
2. **Sem Devin:** sem Devin não há `sessions.db` — o extra desaparece
   completamente.
3. **Seguro por construção:** o parsing passa pelo gate de versão de schema
   do `devin-internals-spec`, por isso uma nova migração do Devin falha
   ruidosamente em vez de corromper o teu rollup em silêncio.

## Instalação

Requer Python ≥ 3.10 e `pipx`. **Windows (PowerShell):** instale `pipx` com `py -m pip install --user pipx`, execute `py -m pipx ensurepath` e reabra o terminal. **Linux (Debian/Ubuntu):** execute `sudo apt install pipx python3-venv` e `pipx ensurepath`; reabra o terminal. Noutras distribuições Linux, instale `pipx` pelo gestor de pacotes.

```bash
pipx install "devin-pm @ git+https://github.com/Icaro0310/devin-pm.git"
```

Para desenvolvimento:

```bash
pip install -e ".[dev]"
pytest
```

## Uso

```bash
devin-pm status                          # tabela rollup por projeto
devin-pm status --json                   # o mesmo, legível por máquina
devin-pm status --vscdb                  # também funde sessões GUI (auto-detect)
devin-pm status --vscdb path/state.vscdb # fixa o store da GUI
devin-pm report --project my-repo        # relatório de status em markdown
devin-pm report                          # relatório global, todos os projetos
devin-pm report --project x --out x.md   # escreve para ficheiro
devin-pm milestones --project my-repo    # lista de milestones + % feito
devin-pm registry --out registry.json    # registo legível por máquina
devin-pm verify                          # diff projetos vs registry do hub
devin-pm verify --json                   # o mesmo, legível por máquina
```

`--sessions-db PATH` sobrepõe a localização da base de dados em todos os
subcomandos; caso contrário o `devin-pm` auto-detecta
`%APPDATA%/devin/cli/sessions.db` (a variável `DEVIN_PM_SESSIONS_DB` também
funciona). Todas as leituras são read-only.

### Sessões da GUI (`--vscdb`)

A app Desktop grava as ligações sessão→workspace no store Electron
`<config>/Devin/User/globalStorage/state.vscdb` — chaves do tipo
`windsurfSpace.sessionWorkspace/<backend>/<slug>` com JSON
`{workspaceId, label, folders[], lastUpdated}`. Passar `--vscdb` em
qualquer subcomando funde-as no mesmo agrupamento por projeto (PM-1):

```bash
devin-pm status --vscdb                # flag simples: auto-detecta
devin-pm report --vscdb PATH           # fixa um state.vscdb específico
```

Sessões GUI não têm transcript — agrupam por `workspaceId` (caindo para o
primeiro `folders[]`, depois `label`) e são marcadas como gui-sourced em
todo o lado: status `gui` nos relatórios, coluna `GUI` na tabela de
`status`, coluna `source` nas tabelas de sessões e contagem
`gui_sessions` no output `--json`/`registry`. Um `--vscdb` simples sem
store encontrado avisa e continua só com o `sessions.db`; um `PATH`
explícito inexistente sai com `2`. `DEVIN_PM_STATE_VSCDB` sobrepõe a
auto-detecção. O store é aberto em `mode=ro` — read-only, sempre.

### Normalização de caminhos (chaves de agrupamento)

O mesmo repo pode ficar gravado como `C:\Users\X\repo`,
`/c/Users/X/repo` (MSYS/Git-Bash) ou `\\wsl.localhost\Ubuntu\home\u\repo`
(UNC do WSL). Antes do PM-3 isso dividia um projeto em três grupos. As
chaves de agrupamento agora dobram: `C:\x` ⇄ `C:/x` ⇄ `/c/x` ⇄
`/cygdrive/c/x` (caminhos com drive dobram maiúsculas — o FS do Windows é
case-insensitive), prefixos UNC do WSL mapeiam para o caminho POSIX da
distro, e separadores/barras finais colapsam. O output mantém o caminho
original; só a chave de agrupamento é normalizada. Caminhos POSIX mantêm
as maiúsculas (`/home/u/Foo` ≠ `/home/u/foo`).

### Verificar contra o registry do ecossistema

`devin-pm verify` cruza os projetos que o pm segue com o catálogo
autoritativo do ecossistema em `devin-powerups/registry.json`:

```bash
devin-pm verify --registry ../devin-powerups/registry.json
```

`--registry` usa por defeito `../devin-powerups/registry.json` relativo ao
diretório atual (depois o checkout irmão deste pacote). O relatório tem
três secções:

- **in registry but unknown to pm** — repos catalogados sem sessões nesta
  máquina (informativo, nunca conta como drift);
- **tracked by pm but missing from registry** — projetos com sessões que o
  registry não lista. Contam como drift apenas quando parecem do
  ecossistema (nome `devin-*` ou checkout debaixo do diretório pai do hub);
  os restantes são marcados `[non-ecosystem]`;
- **field drift** — para repos em comum, `name`/`description` lidos do
  `pyproject.toml` do checkout e `url` do remote git `origin` contra os
  valores do registry. Campos não observáveis (sem pyproject, sem remote)
  são ignorados, nunca adivinhados.

`--pm-registry FILE` verifica um documento guardado de
`devin-pm registry --out` em vez de abrir o `sessions.db`. Código de saída:
`1` em drift, `0` quando limpo — serve como gate de manutenção. Tudo é
local e read-only (`sessions.db`, `registry.json`, `pyproject.toml`,
`.git/config`).

### Milestones

Marca uma sessão dando ao título `milestone: <nome>` — isso marca um
milestone no projeto dessa sessão; arquivar (esconder) a sessão marca-o
como feito. Ou lista-os manualmente num `milestones.json` na raiz do
projeto:

```json
{"milestones": [{"name": "M1 — core", "done": true}, "M2 — polish"]}
```

Entradas do ficheiro ganham das detetadas por sessão em caso de colisão
de nome.

### Códigos de saída

`0` ok · `1` erro de leitura/parse (`verify`: também drift encontrado) ·
`2` db em falta / projeto desconhecido / inputs em falta.

## Funciona só com o Devin (modo Devin-only)

O devin-pm calcula os relatórios diretamente do `sessions.db` local
(`%APPDATA%\devin\cli\sessions.db` no Windows,
`~/.local/share/devin/cli/sessions.db` no Linux). A saída vai para o terminal
ou para um ficheiro local — nada externo é contactado, e não há VM, fila de
mensagens ou servidor de modelos envolvido.

## Suporte de plataformas

Testado em **Windows e Linux** (o CI corre em `windows-latest` +
`ubuntu-latest`). A `sessions.db` do Devin é auto-detetada por
plataforma — `%APPDATA%\devin\` no Windows, `~/.local/share/devin/`
(`XDG_DATA_HOME`) no Linux, `~/Library/Application Support/devin/` no
macOS. Override com a env var `DEVIN_PM_SESSIONS_DB` (ver Uso). O
`state.vscdb` da GUI fica em
`<config>/Devin/User/globalStorage/state.vscdb` (`%APPDATA%` no Windows,
`XDG_CONFIG_HOME`/`~/.config` no Linux); override com
`DEVIN_PM_STATE_VSCDB`.

## Limitações

- **Internals privados e voláteis.** O `sessions.db` é detalhe de
  implementação do Devin; o parsing está gated nas versões de schema
  conhecidas (15–17) e recusa qualquer versão nova em vez de adivinhar.
- **Custo é best-effort.** A DB não regista billing num campo documentado;
  `cogs_json` é instável. Quando não existe campo de custo reconhecível,
  os relatórios mostram `-` e o registo emite `null` — desconhecido, não
  zero.
- **Cobertura GUI é só bindings.** `--vscdb` lê as ligações
  sessão→workspace do `state.vscdb`; os transcripts da GUI
  (`acp-messages/*.db`) não estão cobertos, por isso sessões gui não têm
  detalhe de custo/milestone além de um label `milestone:`.
- **Read-only.** Este projeto nunca escreve nas bases de dados do Devin;
  os únicos ficheiros que escreve são os que pedes (`--out`,
  `milestones.json` é teu para criar).
- **Agrupamento normaliza spellings, não máquinas.** `C:\x` ⇄ `/c/x` e
  prefixos UNC do WSL dobram numa chave, mas `/home/u/repo` vs
  `c:/users/u/repo` ficam distintos — nada no caminho prova que são o
  mesmo diretório. Caminhos POSIX mantêm as maiúsculas.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```

TDD fixtures-first — vê [docs/SPEC.md](docs/SPEC.md) para os contratos de
dados e [CONTRIBUTING.md](CONTRIBUTING.md) para as regras base.

## Quando usar

- Você tem semanas de sessões Devin e quer um rollup por repo — que projetos existem, contagens de sessões, atividade mais recente, status — sem percorrer a lista plana de sessões da app.
- Você quer relatórios de status em Markdown ou um registry JSON para alimentar docs, dashboards ou outras ferramentas (`devin-pm registry --out registry.json`).
- Você acompanha milestones e quer que sejam detetados automaticamente de títulos de sessão `milestone: <name>`, ou curados num ficheiro `milestones.json` na raiz do projeto.
- Você quer rollups estritamente read-only que falham ruidosamente em versões de schema `sessions.db` desconhecidas em vez de as lerem mal em silêncio.

## Quando NÃO usar

- Você precisa dos transcripts das sessões GUI — o `--vscdb` cobre as ligações de workspace do `state.vscdb` (que sessão GUI trabalhou em que workspace), não os stores de mensagens `acp-messages/*.db`.
- Você precisa de rollups fiáveis de custo ou billing — a DB não tem campo de custo documentado; os relatórios mostram `-`/`null` onde é desconhecido, nunca uma estimativa.
- Você precisa de estado de sessões ao vivo — o devin-pm reporta sobre o snapshot do `sessions.db` no momento da leitura; para atividade ao vivo veja o [`devin-office`](https://github.com/Icaro0310/devin-office).

## FAQ

**O que é o devin-pm?** Um CLI que transforma o `sessions.db` plano do Devin numa vista de gestão de projetos: tabelas de status por repositório, relatórios Markdown, tracking de milestones e um registry legível por máquina. É read-only — os únicos ficheiros que escreve são os relatórios que pede.

**Como as sessões são agrupadas em projetos?** Por diretório de trabalho: cada sessão regista onde correu, e sessões que partilham esse caminho tornam-se um projeto. A chave de agrupamento normaliza spellings de caminho — `C:\x`, `/c/x` e `/cygdrive/c/x` dobram juntos (case-insensitive em caminhos com drive), e `\\wsl.localhost\<distro>\…` mapeia para o caminho POSIX da distro — enquanto caminhos POSIX mantêm as maiúsculas. Com `--vscdb`, as ligações sessão→workspace da GUI entram no mesmo agrupamento e são marcadas `gui`.

**Como marco um milestone?** Dê a um título de sessão o nome `milestone: <name>` — isso marca-o no projeto da sessão, e arquivar (esconder) a sessão marca-o como feito. Em alternativa, liste milestones em `milestones.json` na raiz do projeto; entradas do ficheiro vencem em colisão de nomes.

**Porque o meu relatório mostra `-` para custo?** Porque o `sessions.db` não regista billing num campo documentado. Onde não existe custo reconhecível, o devin-pm reporta `null`/`-` — desconhecido — em vez de imprimir um zero enganador.

## Licença

MIT — vê [LICENSE](LICENSE).
