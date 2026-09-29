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

```bash
pipx install devin-doctor
```

(requer Python ≥ 3.10)

## Uso

```bash
devin-doctor check                    # diagnostica o data dir padrão
devin-doctor check --data-dir D:\devin-backup
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

## Limitações

- **Amarrado à versão.** O parsing segue o `devin-internals-spec` (schema
  v15–v17). Um schema mais novo reporta FAIL — "versão desconhecida" — de
  propósito, em vez de ler errado em silêncio.
- **Somente leitura.** Sugere correções mas nunca toca no data dir. `--fix`
  para os itens seguros está planeado (ver `STATUS.md`).
- **Stores bloqueados.** Com o Devin aberto, as DBs podem reportar
  `SQLITE_BUSY` — fecha o Devin e corre de novo.
- Windows + Linux são os alvos testados; os caminhos de macOS existem mas
  não estão verificados.

## Desenvolvimento

```bash
pip install -e ".[dev]"
python -m pytest
```

Os testes correm inteiramente sobre fixtures sintéticas geradas por
`devin_internals.fixtures` — nenhum dado de sessão real é lido ou necessário.
`scripts/make_fixture.py <dir>` cria um data dir de fixture para corridas
manuais.

## Licença

MIT — vê [LICENSE](LICENSE).
