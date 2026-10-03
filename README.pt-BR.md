# devin-graph

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

Um grafo de conhecimento sobre as sessões do Devin: sessões, projetos,
ficheiros e ferramentas viram nós — consultável ("que sessões tocaram o
ficheiro X?", "de que ferramentas o projeto Y depende?") e exportável para
visualização.

## O problema

Depois de dezenas de sessões do Devin perde-se o fio: que sessões tocaram
aquele ficheiro de configuração, de que ferramentas um projeto depende, que
projetos partilham os mesmos ficheiros. Os dados existem no `sessions.db`
(`tool_call_state` regista cada chamada do agente) mas não há como consultar
entre sessões — só o scroll sessão a sessão na UI.

## Trabalho anterior (prior art)

- Grafos de conhecimento de código (Sourcegraph, índices estilo Glean) mapeiam
  *código*, não *atividade do agente*; não sabem o que as tuas sessões de IA
  tocaram.
- `devin-internals-spec` fornece o schema + parsers read-only tipados em que
  esta ferramenta se apoia; `devin-history` exporta a mesma store para notas
  mas sem estrutura entre sessões.
- Dava para escrever SQL à mão — mas o formato de `tool_call_json` não é
  documentado e muda; aqui é extraído defensivamente num único sítio.

## O que o torna Devin-native

As arestas vêm de **ground truth, não de prosa**: arestas `file_touched` são
extraídas dos payloads de `tool_call_state` (paths de ficheiros em chamadas de
ferramentas fs/terminal) e ancoradas no `working_directory` da sessão. Esses
dados simplesmente não existem fora da store do Devin — sem Devin, não há
grafo para construir. Mudanças de schema são travadas pelo detector de versão
do `devin-internals-spec`.

## Instalação

Requer Python ≥ 3.10 e `pipx`. **Windows (PowerShell):** instale `pipx` com `py -m pip install --user pipx`, execute `py -m pipx ensurepath` e reabra o terminal. **Linux (Debian/Ubuntu):** execute `sudo apt install pipx python3-venv` e `pipx ensurepath`; reabra o terminal. Noutras distribuições Linux, instale `pipx` pelo gestor de pacotes.

```bash
pipx install "devin-graph @ git+https://github.com/Icaro0310/devin-graph.git"
```

(Release PyPI está no roadmap M2; Python ≥ 3.10 necessário.)

## Uso

```bash
# constrói o grafo (auto-deteta sessions.db por SO) — seguro re-executar:
# sessões sem alterações são saltadas
devin-graph build --graph graph.db

# consultas prontas
devin-graph query file "src/app.py"        --graph graph.db
devin-graph query tool "execute"           --graph graph.db
devin-graph query project "my-repo"        --graph graph.db
devin-graph query projects-graph           --graph graph.db --json

# dump compatível com D3: {"meta", "nodes", "edges"}
devin-graph export --format json --graph graph.db --out graph.json
```

A correspondência é tolerante (`src/app.py` encontra
`/repo/alpha/src/app.py`); tudo tem `--json`. A DB de origem é aberta em
`mode=ro` e nunca é escrita — os testes garantem que o hash não muda.

## Funciona só com o Devin (modo Devin-only)

O devin-graph constrói o `graph.db` localmente a partir das stores de sessão
do Devin — o pipeline inteiro é offline. Nota que a base de dados derivada
contém o mesmo conteúdo sensível das sessões (prompts, caminhos, comandos):
mantém-na privada como os originais.

## Suporte de plataformas

Testado em **Windows e Linux** (o CI corre em `windows-latest` +
`ubuntu-latest`). A base CLI é auto-detetada: `%APPDATA%/devin/cli/sessions.db`
no Windows e `$XDG_DATA_HOME/devin/cli/sessions.db` no Linux (por omissão
`~/.local/share/devin/cli/sessions.db`). A localização antiga `~/.config/devin`
também é verificada. Usa `--sessions-db` para sobrepor.

## Limitações

- **Dependente do schema.** Apenas `sessions.db` schema v15–v17; mais recente
  falha em voz alta (atualiza `devin-internals-spec` primeiro).
- **Extração de paths heurística.** `tool_call_*_json` é um formato instável e
  opaco: paths são recolhidos de chaves de path e de tokens tipo-path em
  comandos — best-effort, não contratual. Um formato de payload novo pode gerar
  arestas parciais.
- **Só sessões CLI (M1).** Sessões GUI (`acp-messages/*.db`) e `state.vscdb`
  estão planeados para M2.
- **Não é um índice de código.** Nós são ficheiros *que o agente tocou*, não o
  conteúdo do repo; sem conhecimento de símbolos/AST.
- **Read-only por design** nas stores do Devin; `graph.db` é a única coisa
  que escreve.

## Desenvolvimento

```bash
pip install -e ".[dev]"
python -m pytest
```

Fixtures são gerados em tempo de teste por `devin_internals.fixtures` (DDL v17
real, linhas sintéticas) — nenhum fixture binário é commitado. Vê
[docs/SPEC.md](docs/SPEC.md) para o modelo do grafo e
[STATUS.md](STATUS.md) para o roadmap.

## Licença

MIT — vê [LICENSE](LICENSE).
