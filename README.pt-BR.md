<div align="center">

<img src="assets/banner.svg" alt="devin-search" width="100%"/>

</div>

# devin-search

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

Pesquisa full-text em todas as tuas sessões do Devin — encontra aquele
comando, aquela mensagem de erro, aquele caminho de ficheiro ou aquela
decisão de meses atrás em menos de um segundo.

## O problema

O Devin guarda todo o histórico de sessões em bases SQLite locais
(`sessions.db`, `User/acp-messages/*.db`) — mas não oferece forma de
pesquisar nelas. Lembras-te que o Devin corrigiu um teste instável ou correu
um `kubectl` específico há três semanas, e a única forma de voltar lá é
percorrer sessões uma a uma. Um `grep` genérico sobre as bases cruas apanha
sobretudo ruído JSON e não sabe quem disse o quê.

## Trabalho anterior (prior art)

- Pesquisa full-text sobre histórico de chat/agentes é bem estabelecida:
  tudo aqui usa o motor **FTS5** nativo do SQLite com ranking **BM25** — a
  mesma abordagem de ferramentas tipo ripgrep, clientes de email e
  `sqlite-utils`.
- **tokmesh** e **UniSessions** documentam/fazem parse do `sessions.db`
  da CLI; o schema em si é acompanhado pelo
  [`devin-internals-spec`](https://github.com/Icaro0310/devin-internals-spec),
  que este projeto usa para acesso versionado e read-only.
- **devin-history** (repo irmão) exporta sessões para Markdown/JSON; o
  devin-search complementa-o com lookup instantâneo e ranqueado em vez de
  um dump estático.

## O que o torna Devin-native

Os resultados são **etiquetados por role e ligados à sessão**, não hits de
grep crus. O indexador percebe a estrutura real de mensagens do Devin através
dos parsers tipados do `devin-internals-spec`: prompts do utilizador vs
respostas do assistente vs tool calls (incluindo comandos shell de
`prompt_history` e sessões GUI `acp-messages`), cada um com o seu working
directory e um `ref` para a linha exata da fonte. E como o schema já teve 17
migrações, a indexação **falha ruidosamente** numa versão desconhecida em vez
de ler errado em silêncio.

## Instalação

Requer Python ≥ 3.10 e `pipx`. **Windows (PowerShell):** instale `pipx` com `py -m pip install --user pipx`, execute `py -m pipx ensurepath` e reabra o terminal. **Linux (Debian/Ubuntu):** execute `sudo apt install pipx python3-venv` e `pipx ensurepath`; reabra o terminal. Noutras distribuições Linux, instale `pipx` pelo gestor de pacotes.

```bash
pipx install "devin-search @ git+https://github.com/Icaro0310/devin-search.git"
```

(Release PyPI está no roadmap M2; Python ≥ 3.10 necessário.)

## Uso

```bash
# constrói/atualiza o índice (auto-deteta as stores do Devin; seguro re-correr —
# só as linhas novas são indexadas de cada vez)
devin-search index

# pesquisa tudo
devin-search query "kubectl delete pod"

# filtros: role, projeto, data, limite — --json em todos os comandos
devin-search query "TypeError" --role assistant --project myrepo
devin-search query "migration" --since 2026-09-01 --limit 5 --json

# liga os hits às notas exportadas pelo devin-history
devin-search query "kubectl" --history-dir ~/notas/devin-history
```

Os hits aparecem como `WHEN · ROLE · PROJECT · SESSION · SNIPPET` com o match
entre `«»`; cada hit traz um `ref` (ex.: `node:1234`, `acp:file.db:7`) que
aponta para a linha exata da fonte.

Com `--history-dir <dir>` a apontar para um diretório de export do
[`devin-history`](https://github.com/Icaro0310/devin-history), cada hit cuja
sessão tem uma nota exportada ganha uma linha `note: <path>` debaixo da sua
linha (e um campo `history_note` em `--json`). As notas são encontradas pelo
nome de ficheiro `<YYYY-MM-DD>_<session-id>.md` que o devin-history escreve
(exports `.json` servem de fallback). Uma nota em falta não gera link nem
erro — a flag é puramente aditiva.

## Funciona só com o Devin (modo Devin-only)

O devin-search constrói e consulta um índice totalmente local sobre as stores
de sessão do Devin. Nada é enviado para lado nenhum; o índice vive no teu
disco junto dos dados que cobre.

## Suporte de plataformas

Testado em **Windows e Linux** (o CI corre em `windows-latest` +
`ubuntu-latest`). A base CLI é auto-detetada a partir de
`%APPDATA%/devin/cli/sessions.db` no Windows e
`$XDG_DATA_HOME/devin/cli/sessions.db` no Linux (por omissão
`~/.local/share/devin/cli/sessions.db`). Os logs ACP são procurados em
`$XDG_CONFIG_HOME/Devin/User/acp-messages` (por omissão
`~/.config/Devin/User/acp-messages`). A estrutura antiga `~/.config/devin`
também é verificada. Usa `--sessions-db` ou `--acp-dir` para sobrepor.

## Limitações

- **Schema-gated.** Só `sessions.db` schema v15–v17 é aceite; versões mais
  novas falham ruidosamente (atualiza o `devin-internals-spec` primeiro).
- **Payloads opacos.** Os formatos `chat_message`, `tool_call_*_json` e
  `payload` do acp são não documentados/instáveis — a extração de texto é
  best-effort e tolerante, não contratual.
- **Só pesquisa por palavra-chave (M1).** BM25 sobre tokens — sem sinónimos
  nem embeddings; pesquisa semântica é candidata opt-in para M2.
- **Lag de deleções.** Linhas novas entram incrementalmente, mas linhas
  apagadas a meio da tabela podem ficar no índice até `--rebuild` (fontes
  podadas na cauda são detetadas e re-indexadas automaticamente).
- **Read-only por design** — a ferramenta nunca escreve nas stores do Devin;
  o único ficheiro que cria é `search.db`.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```

Fixtures são geradas em tempo de teste por `devin_internals.fixtures` (DDL
v17 real, linhas sintéticas) — nenhum fixture binário é commitado.

## Quando usar

- Você lembra-se que o Devin correu um comando, bateu num erro, tocou num ficheiro ou tomou uma decisão, e percorrer sessões uma a uma é demasiado lento.
- Você quer resultados rankeados etiquetados por papel (user / assistant / tool call) com um `ref` de volta à linha de origem exata.
- O seu histórico de sessões tem de ficar em disco — o índice é totalmente local, sem telemetria, sem chamadas de rede.
- Você quer indexação incremental: re-executar `devin-search index` só apanha linhas novas.

## Quando NÃO usar

- Você precisa de pesquisa semântica ou com sinónimos — o M1 é BM25 por keywords apenas; embeddings são candidato opt-in no M2.
- Você precisa de *analítica* de sessões (custo, tokens, atividade) — use `devin-metrics`; ou queries de relações — use `devin-graph`.
- O schema do seu `sessions.db` está fora de v15–v17 — a indexação recusa ruidosamente em vez de ler mal.

## FAQ

**O que é o devin-search?** Um motor local de pesquisa full-text sobre o seu histórico de sessões Devin. Indexa os stores SQLite do Devin com FTS5/BM25 e responde a queries como `devin-search query "kubectl delete pod"` em menos de um segundo, com resultados etiquetados por papel e ligados à linha de origem.

**O devin-search envia os meus dados de sessão para algum lado?** Não. Tudo corre localmente: lê os stores do Devin em read-only e escreve um único índice `search.db` junto aos seus dados. Não há chamadas de rede nem telemetria.

**Ele escreve ou modifica as bases de dados do Devin?** Não. Os stores do Devin são abertos read-only por design; o único ficheiro que o devin-search cria é o seu próprio índice `search.db`.

**Como é diferente do `devin-history`?** O devin-history exporta sessões para ficheiros Markdown/JSON estáticos. O devin-search complementa-o com pesquisa rankeada instantânea sobre todas as sessões, sem exportar nada.

## Licença

MIT — vê [LICENSE](LICENSE).
