# devin-history

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

Exporta e audita o histórico de sessões do Devin Desktop — transforma a
`sessions.db` local em notas Markdown prontas para Obsidian, num dump JSON
pesquisável e num relatório de auditoria.

## O problema

O Devin Desktop guarda todo o histórico de sessões numa base SQLite local
(`%APPDATA%/devin/cli/sessions.db`) — e em mais lado nenhum. Não há botão de
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

# tudo tem --json; aponta para uma DB específica com --sessions-db
devin-history audit --sessions-db caminho/para/sessions.db --json
```

As notas são idempotentes: cada ficheiro embute o marcador `last_activity`
da sessão, por isso re-runs saltam sessões inalteradas (`--all` força
re-escrita, `--dry-run` pré-visualiza).

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
- **Só sessões CLI (M1).** Sessões GUI em `User/acp-messages/*.db`, session
  locks e correlação de logs ficam para M2.
- **Read-only por design** — a ferramenta nunca escreve nos stores do Devin.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```

Fixtures são geradas em tempo de teste pelo `devin_internals.fixtures`
(DDL v17 real, linhas sintéticas) — sem fixtures binárias commitadas.

## Licença

MIT — vê [LICENSE](LICENSE).
