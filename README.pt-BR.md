<div align="center">

<img src="assets/banner.svg" alt="devin-history" width="100%"/>

<a href="https://github.com/Icaro0310/devin-history/actions/workflows/tests.yml"><img src="https://github.com/Icaro0310/devin-history/actions/workflows/tests.yml/badge.svg" alt="tests"/></a>


</div>

# devin-history

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

Exporta e audita o histórico de sessões do Devin Desktop — transforma a
`sessions.db` local em notas Markdown prontas para Obsidian, num dump JSON
pesquisável e num relatório de auditoria. Os metadados das sessões GUI
(`state.vscdb`) também são exportados como notas.

## O problema

O Devin Desktop guarda o histórico de sessões numa base SQLite local
(`%APPDATA%/devin/cli/sessions.db` no Windows ou
`$XDG_DATA_HOME/devin/cli/sessions.db` no Linux; por omissão
`~/.local/share/devin/cli/sessions.db`) — e em mais lado nenhum. Não há botão de
export: quando uma sessão sai da UI (ou é limpa pela app), os prompts, as
respostas e os tool calls ficam efetivamente perdidos. Não dá para pesquisar
sessões antigas, responder "o que pedi ao Devin no mês passado" nem auditar
como o agente tem sido usado entre projetos.

## Trabalho anterior (prior art)

- **tokmesh** e **UniSessions** documentam/fazem parsing da `sessions.db`; o
  schema em si é acompanhado pelo
  [`devin-internals-spec`](https://github.com/Icaro0310/devin-internals-spec).
- Este projeto porta dois scripts provados que viviam no workspace do
  orquestrador (`legacy/`): `devin-history-export.py` (DB → notas Obsidian)
  e `audit_sessions.py` (auditoria lifetime → CSV + relatório). Foram
  reescritos como módulos de biblioteca — mesma lógica, testes de verdade.
- Também dá para correr queries `sqlite3` à mão — mas aí adivinha-se o
  schema a cada update do Devin.

## O que o torna Devin-native

Entende os stores reais do Devin em vez de adivinhar SQL: abre a
`sessions.db` através dos parsers tipados do `devin-internals-spec` e
**recusa ruidosamente** quando a versão do schema é uma que nunca viu (o
store já teve 17 migrações). O export sabe de sessões `hidden`, threads
interrompidas (último nó = user), falhas em `tool_call_state` e timestamps
epoch-milissegundos — detalhes que um dump SQLite genérico perde.

## Instalação

Requer Python ≥ 3.10 e `pipx`. **Windows (PowerShell):** instale `pipx` com `py -m pip install --user pipx`, execute `py -m pipx ensurepath` e reabra o terminal. **Linux (Debian/Ubuntu):** execute `sudo apt install pipx python3-venv` e `pipx ensurepath`; reabra o terminal. Noutras distribuições Linux, instale `pipx` pelo gestor de pacotes.

```bash
pipx install "devin-history @ git+https://github.com/Icaro0310/devin-history.git"
```

(Release PyPI está no roadmap M2; requer Python ≥ 3.10.)

## Uso

```bash
# tabela rápida de sessões (auto-detecta %APPDATA%/devin/cli/sessions.db)
devin-history list

# uma nota Obsidian por sessão + index.md — seguro re-correr (incremental)
devin-history export --out ~/ObsidianVault/Sessions

# dump JSON pesquisável em vez de Markdown
devin-history export --out dump/ --format json

# auditoria: agrupamentos por status/tipo/projeto/período + anomalias, CSV opcional
devin-history audit --csv audit.csv

# sessões GUI: notas de metadados (slug, workspace, folders, lastUpdated) +
# index.json — o GUI não guarda transcript local, só os metadados existem
devin-history export-gui --out ~/ObsidianVault/Sessions/gui

# tudo tem --json; aponta para uma DB específica com --sessions-db/--vscdb
devin-history audit --sessions-db caminho/para/sessions.db --json
devin-history export-gui --vscdb caminho/para/state.vscdb --out gui-notes/
```

As notas são idempotentes: cada ficheiro embute o marcador `last_activity`
da sessão, por isso re-runs saltam sessões inalteradas (`--all` força
re-escrita, `--dry-run` pré-visualiza). O `index.md`/`index.json` na raiz
traz um bloco de estatísticas — total de sessões, intervalo de datas e
totais por projeto e por tipo de mensagem (user/assistant/tool) — junto dos
links agrupados.

O `export-gui` lê o store Electron `state.vscdb` (auto-detetado em
`User/globalStorage/` do diretório de config do Devin, override com
`--vscdb`) e grava uma nota por binding `windsurfSpace.sessionWorkspace/*`:
slug, label, backend, workspaceId, folders, `lastUpdated` e `lastAccessed`
quando derivável via `windsurfSpace.resourceToSpace` +
`windsurfSpace.metadata`. É read-only no `state.vscdb`, embute a mesma
proveniência (`machine_id`/`profile`) e grava um `index.json`.

## Funciona só com o Devin (modo Devin-only)

Tudo o que o devin-history faz acontece na tua máquina: lê o `sessions.db` e
grava exports em Markdown/JSON numa pasta à tua escolha. Sem rede, sem
serviço externo — o layout estilo Obsidian é só um formato; o Obsidian em si
não é necessário.

Um cuidado em máquinas restritas: os exports contêm prompts, caminhos e
comandos em bruto, que podem incluir segredos. Mantém a pasta de export
privada, define uma retenção e corre o
[`devin-redact`](https://github.com/Icaro0310/devin-redact) antes de partilhar
um export.

## Suporte de plataformas

Testado em **Windows e Linux** (o CI corre em `windows-latest` +
`ubuntu-latest`). A base CLI é auto-detetada: `%APPDATA%/devin/cli/sessions.db`
no Windows e `$XDG_DATA_HOME/devin/cli/sessions.db` no Linux (por omissão
`~/.local/share/devin/cli/sessions.db`). A localização antiga `~/.config/devin`
também é verificada. macOS usa `~/Library/Application Support/devin/`.
Override com `--sessions-db` (ver Uso). O `state.vscdb` do GUI é
auto-detetado em `<config>/User/globalStorage/state.vscdb` (diretórios
`Devin`/`devin`); override com `--vscdb`.

## Limitações

- **Gated por schema.** Só `sessions.db` schema v15–v17 é aceite; qualquer
  versão mais nova falha ruidosamente em vez de ler mal (atualiza o
  `devin-internals-spec` primeiro).
- **Payloads opacos.** Os formatos internos de `chat_message` e
  `tool_call_*_json` são indocumentados e instáveis — o decoding é
  best-effort e tolerante, não contratual.
- **Status inferido.** A DB não tem coluna de estado final; "concluída" /
  "interrompida" / "abandonada" são heurísticas (ver `docs/SPEC.md` §4).
- **Sem billing.** Dados de tokens/custo não são guardados localmente; só
  existe `num_tokens_preceding` (tamanho de contexto).
- **Sessões GUI são só metadados.** O `export-gui` exporta os bindings
  sessão↔workspace guardados no `state.vscdb` (slug, label, folders,
  timestamps) — o GUI não guarda transcript local. Transcripts GUI em
  `User/acp-messages/*.db`, session locks e correlação de logs ficam
  para M2.
- **Read-only por design** — a ferramenta nunca escreve nos stores do Devin.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```

Fixtures são geradas em tempo de teste pelo `devin_internals.fixtures`
(DDL v17 real, linhas sintéticas) — sem fixtures binárias commitadas.

## Quando usar

- Você quer o seu histórico de sessões Devin fora da app antes que as sessões desapareçam ou sejam podadas — não há botão de export embutido.
- Você mantém um vault Obsidian (ou qualquer pasta Markdown) e quer uma nota por sessão mais um `index.md`, idempotente entre re-execuções.
- Você precisa de uma auditoria de vida inteira: agrupamentos por status, tipo de tarefa, projeto e período, mais deteção de anomalias (sessões vazias, órfãs, de longa duração).
- Você quer um export determinístico e read-only que possa agendar — nada é alguma vez escrito de volta nos stores do Devin.

## Quando NÃO usar

- Você precisa de pesquisa rankeada instantânea em vez de um export estático — use o [`devin-search`](https://github.com/Icaro0310/devin-search) sobre a mesma base de dados.
- Você precisa dos *transcripts* das sessões GUI — o `export-gui` exporta os metadados do `state.vscdb`; os stores de transcript `acp-messages/*.db` ficam para o M2.
- O schema do seu `sessions.db` é mais recente que v17 — a ferramenta recusa ruidosamente em vez de ler mal; atualize o `devin-internals-spec` primeiro.

## FAQ

**O que é o devin-history?** Um CLI que exporta o `sessions.db` local do Devin para notas Markdown prontas para Obsidian, um dump JSON ou um relatório de auditoria. Deteta a base automaticamente no Windows, Linux e macOS e nunca escreve nos stores do Devin.

**É seguro re-executar o export?** Sim. Cada nota embute o marcador `last_activity` da sessão, por isso sessões inalteradas são saltadas nas re-execuções. `--all` força reescrita e `--dry-run` faz preview sem escrever.

**Ele envia os meus dados de sessão para algum lado?** Não. Tudo acontece na sua máquina: lê a base local e escreve ficheiros numa pasta à sua escolha. Note que os exports contêm prompts e caminhos crus — mantenha a pasta de output privada ou corra `devin-redact` antes de partilhar.

**Porque é que ele se recusa a ler a minha base de dados?** Porque a versão do schema está fora do intervalo suportado v15–v17. O store já teve 17 migrações; o devin-history falha ruidosamente em versões desconhecidas em vez de interpretar mal o seu histórico em silêncio.

## Licença

MIT — vê [LICENSE](LICENSE).
