<div align="center">

<img src="assets/banner.svg" alt="devin-doctor" width="100%"/>

<a href="https://github.com/Icaro0310/devin-doctor/actions/workflows/tests.yml"><img src="https://github.com/Icaro0310/devin-doctor/actions/workflows/tests.yml/badge.svg" alt="tests"/></a>


</div>

# devin-doctor

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

O `devin-doctor` diagnostica uma instalação do Devin Desktop — um comando que
verifica os stores locais, versões de schema, ficheiros de config e uso de
disco, e depois imprime um relatório de saúde com sugestões concretas de
correção. Somente leitura, sempre.

## O problema

O Devin guarda bastante estado local: um `sessions.db` versionado, um
`acp-messages/*.db` por sessão GUI, um `state.vscdb` de chave-valor,
`credentials.toml` e ficheiros de config JSONC. Quando algo quebra ou incha —
um schema que a ferramenta não conhece, uma base bloqueada, um ficheiro de
hooks inválido, um store de sessões de 700 MiB — nada te avisa. Descobres
indiretamente: histórico em falta, erros de autenticação, falta de disco.

O `devin-doctor` é o `brew doctor` dessa instalação.

## Trabalho anterior (prior art)

- `brew doctor` / `flutter doctor` — o género: um comando, várias
  verificações, PASS/WARN/FAIL com sugestões de correção. Este projeto adapta
  o padrão; não reinventa a roda.
- [`devin-internals-spec`](https://github.com/Icaro0310/devin-internals-spec)
  — fornece o detetor de versão de schema, os parsers read-only dos stores e
  o gerador de fixtures sobre os quais este projeto se apoia.

## O que o torna Devin-native

Entende o layout real do Devin no disco — o ledger de migrações
`refinery_schema_history`, os stores `acp-messages` por sessão, o
`state.vscdb` e o formato de config de hooks/MCP em `.devin/` — coisas que
nenhuma verificação genérica de sistema enxerga. Sem o Devin, não há nada
para diagnosticar.

## Instalação

Requer Python ≥ 3.10 e `pipx`. **Windows (PowerShell):** instale `pipx` com `py -m pip install --user pipx`, execute `py -m pipx ensurepath` e reabra o terminal. **Linux (Debian/Ubuntu):** execute `sudo apt install pipx python3-venv` e `pipx ensurepath`; reabra o terminal. Noutras distribuições Linux, instale `pipx` pelo gestor de pacotes.

```bash
pipx install "devin-doctor @ git+https://github.com/Icaro0310/devin-doctor.git"
```

(Ainda não está publicado no PyPI; a instalação pelo GitHub acima é o caminho suportado.)

## Uso

```bash
devin-doctor check                    # diagnostica o data dir padrão
devin-doctor check --data-dir D:\devin-backup
# Raiz de configuração da UI separada (ex.: Linux)
devin-doctor check --data-dir ~/.local/share/devin --config-dir ~/.config/Devin
devin-doctor check --json             # saída legível por máquina
devin-doctor report --md              # markdown, para colar em issues
```

Cada verificação imprime `PASS`/`WARN`/`FAIL`, um achado de uma linha e uma
sugestão `fix:`. O código de saída é `0` a menos que algo dê `FAIL` (aí `1`).

As cinco verificações:

| verificação | reporta |
|---|---|
| `stores` | presença/ausência, tamanhos e contagens de linhas de `sessions.db`, `acp-messages/*.db`, `state.vscdb` |
| `schema` | versão de schema vs o intervalo suportado (15–17); reconhecimento de layout nos stores sem ledger |
| `health-of-data` | sessões vazias, `message_nodes` órfãos, sessões inativas > `--stale-days`, locks `SQLITE_BUSY` |
| `config` | presença + validade do `credentials.toml` (**valores mascarados**); sanidade de hooks/MCP em `.devin/` |
| `disk` | tamanho total do data dir, maiores DBs, acumulação de `acp-messages` |

## Funciona só com o Devin (modo Devin-only)

O devin-doctor é um diagnóstico puramente local: lê os diretórios de dados do
próprio Devin, não escreve nada e nunca contacta um serviço de rede. Sem VM,
sem Tailscale, sem Ollama, sem Slack — só Devin Desktop e Python. Numa
máquina restrita ou corporativa é a primeira ferramenta mais segura:
instala, corre `devin-doctor`, lê o relatório.

## Suporte de plataformas

Testado em Windows e Linux. No Linux, os dados de sessão usam
`$XDG_DATA_HOME/devin` (normalmente `~/.local/share/devin`) e os stores da UI
usam `$XDG_CONFIG_HOME/Devin` (normalmente `~/.config/Devin`). No Windows,
usam `%APPDATA%\devin` e `%APPDATA%\Devin`. Use `--data-dir` e `--config-dir`
se os stores estiverem noutro local. macOS não está verificado.

## Limitações

- **Amarrado à versão.** O parsing segue o `devin-internals-spec` (schema
  v15–v17). Um schema mais novo reporta FAIL — "versão desconhecida" — de
  propósito, em vez de ler errado em silêncio.
- **Somente leitura.** Sugere correções mas nunca toca no data dir. `--fix`
  para os itens seguros está planeado (ver `STATUS.md`).
- **Stores bloqueados.** Com o Devin aberto, as DBs podem reportar
  `SQLITE_BUSY` — fecha o Devin e corre de novo.
- Os caminhos de macOS existem, mas não são verificados pelo CI.

## Desenvolvimento

```bash
pip install -e ".[dev]"
python -m pytest
```

Os testes correm inteiramente sobre fixtures sintéticas geradas por
`devin_internals.fixtures` — nenhum dado de sessão real é lido ou necessário.
`scripts/make_fixture.py <dir>` cria um data dir de fixture para corridas
manuais.

## Quando usar

- O Devin está a comportar-se mal — histórico em falta, erros de auth, pressão de disco — e você quer um comando para localizar a causa.
- Você quer um health check antes de depurar: cinco checks (stores, schema, saúde dos dados, config, disco), cada um com uma sugestão `fix:`.
- Você precisa de um relatório pronto a colar num bug report: `devin-doctor report --md`.
- Você está numa máquina restrita: é read-only e nunca contacta a rede.

## Quando NÃO usar

- Você quer que ele repare coisas — é read-only; `--fix` para itens seguros está planeado.
- O seu schema do Devin é mais recente que v17 — ele reporta FAIL "unknown version" em vez de ler mal.
- O Devin está a correr e as DBs estão bloqueadas — feche o Devin e re-execute para limpar `SQLITE_BUSY`.

## FAQ

**Como verifico se os dados locais da minha instalação do Devin estão saudáveis?** Execute `devin-doctor check`. Ele inspeciona `sessions.db`, `acp-messages/*.db`, `state.vscdb`, `credentials.toml` e o uso de disco, imprimindo `PASS`/`WARN`/`FAIL` por check com uma sugestão `fix:`. O exit code é `0` a menos que algo falhe com FAIL.

**O devin-doctor é seguro? Vai modificar os meus dados?** É estritamente read-only — abre os stores do Devin para leitura, não escreve nada no diretório de dados e nunca contacta um serviço de rede. O check de config mascara valores de credenciais no output. Correções são sugeridas como texto, nunca aplicadas.

**O que significa "unknown schema version"?** O schema do `sessions.db` do Devin é versionado; o devin-doctor entende v15–v17 via devin-internals-spec. Uma versão mais recente produz um FAIL deliberado em vez de uma leitura silenciosa errada — atualize a ferramenta ou o devin-internals-spec.

## Licença

MIT — vê [LICENSE](LICENSE).
