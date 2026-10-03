<div align="center">

<img src="assets/banner.svg" alt="devin-pm" width="100%"/>

</div>

# devin-pm

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

Um gestor de projetos sobre as tuas sessões do Devin — lê o `sessions.db`,
agrupa o trabalho por repositório/projeto e gera relatórios de status,
milestones e um registo de projetos em formato legível por máquina.

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
devin-pm report --project my-repo        # relatório de status em markdown
devin-pm report                          # relatório global, todos os projetos
devin-pm report --project x --out x.md   # escreve para ficheiro
devin-pm milestones --project my-repo    # lista de milestones + % feito
devin-pm registry --out registry.json    # registo legível por máquina
```

`--sessions-db PATH` sobrepõe a localização da base de dados em todos os
subcomandos; caso contrário o `devin-pm` auto-detecta
`%APPDATA%/devin/cli/sessions.db` (a variável `DEVIN_PM_SESSIONS_DB` também
funciona). Todas as leituras são read-only.

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

`0` ok · `1` erro de leitura/parse · `2` db em falta / projeto desconhecido.

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
macOS. Override com a env var `DEVIN_PM_SESSIONS_DB` (ver Uso).

## Limitações

- **Internals privados e voláteis.** O `sessions.db` é detalhe de
  implementação do Devin; o parsing está gated nas versões de schema
  conhecidas (15–17) e recusa qualquer versão nova em vez de adivinhar.
- **Custo é best-effort.** A DB não regista billing num campo documentado;
  `cogs_json` é instável. Quando não existe campo de custo reconhecível,
  os relatórios mostram `-` e o registo emite `null` — desconhecido, não
  zero.
- **Só sessões CLI.** Sessões da GUI/Desktop (`acp-messages/*.db`) não
  estão cobertas no M1.
- **Read-only.** Este projeto nunca escreve nas bases de dados do Devin;
  os únicos ficheiros que escreve são os que pedes (`--out`,
  `milestones.json` é teu para criar).
- **Agrupamento é por string.** Dois caminhos que diferem só em maiúsculas
  são projetos diferentes (correto em POSIX; edge documentado no Windows).

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```

TDD fixtures-first — vê [docs/SPEC.md](docs/SPEC.md) para os contratos de
dados e [CONTRIBUTING.md](CONTRIBUTING.md) para as regras base.

## Licença

MIT — vê [LICENSE](LICENSE).
