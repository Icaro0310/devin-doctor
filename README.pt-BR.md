<div align="center">

<img src="assets/banner.svg" alt="devin-graph" width="100%"/>

<a href="https://github.com/Icaro0310/devin-graph/actions/workflows/ci.yml"><img src="https://github.com/Icaro0310/devin-graph/actions/workflows/ci.yml/badge.svg" alt="ci"/></a>


</div>

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
devin-graph query shared-files             --graph graph.db
devin-graph query projects-graph           --graph graph.db --json

# dump compatível com D3: {"meta", "nodes", "edges"}
devin-graph export --format json --graph graph.db --out graph.json
```

A correspondência é tolerante (`src/app.py` encontra
`/repo/alpha/src/app.py`); tudo tem `--json`. `query shared-files` lista
cada ficheiro tocado por dois ou mais projetos distintos, com as listas
de projetos e sessões — exportável em JSON como as outras consultas.
A DB de origem é aberta em `mode=ro` e nunca é escrita — os testes
garantem que o hash não muda.

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


Nós `commit` + arestas `produced`/`referenced` atribuem sessões a SHAs git vistos em tool calls (exact quando o SHA aparece num call de `git commit`/`git push`, `seen` senão). `devin-graph sql "SELECT ..."` roda SQL read-only sobre graph.db.


`--vscdb` (auto-detectado no build) adiciona cobertura da GUI: nós `gui_session` indexados pelo slug gerado da sessão, arestas `gui_workspace` para o projeto de workspace, enriquecidos com `lastAccessed` quando um URI de editor em `resourceToSpace` liga um space ao slug. Best-effort: só chaves `windsurfSpace.*` observadas são lidas; chaves desconhecidas/malformadas são ignoradas. `--vscdb none` desativa.


`devin-graph view --out file.html` renderiza o grafo numa página HTML auto-contida (JSON embutido + force layout vanilla-JS — zero CDN, funciona totalmente offline). `--limit` limita os nós (mantém os de maior grau, sinalizado TRUNCATED no cabeçalho).

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

## Quando usar

- Você precisa de perguntas entre sessões: que sessões tocaram o ficheiro X, de que ferramentas o projeto Y depende, que projetos partilham ficheiros.
- Você quer arestas da verdade terrestre — payloads reais de `tool_call_state`, não heurísticas sobre texto de chat.
- Você quer um export de grafo para visualizar atividade do agente (`devin-graph export --format json` produz um dump pronto para D3).
- Você quer builds incrementais — re-executar `devin-graph build` salta sessões inalteradas.

## Quando NÃO usar

- Você precisa de um índice de código — os nós são ficheiros que o agente *tocou*, não conteúdo do repo; não há conhecimento de símbolos/AST.
- Você precisa de pesquisa de conteúdo de mensagens (use `devin-search`) ou métricas de uso/custo (use `devin-metrics`).
- Você precisa de dados de sessões GUI — o M1 cobre apenas o `sessions.db` do CLI; `acp-messages` está planeado para o M2.

## FAQ

**O que é o devin-graph?** Uma ferramenta local que transforma a base de sessões do Devin num grafo de conhecimento: sessões, projetos, ficheiros e ferramentas tornam-se nós, com arestas extraídas de payloads reais de tool calls. Consulta-o com `devin-graph query file|tool|project|shared-files` e exporta-o como JSON para visualização.

**Como o devin-graph é diferente do devin-search?** O devin-search encontra texto: hits full-text rankeados dentro do conteúdo das sessões. O devin-graph encontra estrutura: que sessões tocaram que ficheiros, que ferramentas cada projeto usa, e que projetos partilham ficheiros — relações, não correspondências de texto.

**Ele escreve nas bases de dados do Devin?** Não. O `sessions.db` de origem é aberto `mode=ro` e nunca escrito — a suite de testes garante que o seu hash fica inalterado. O único ficheiro que o devin-graph cria é o seu próprio `graph.db`.

## Licença

MIT — vê [LICENSE](LICENSE).
