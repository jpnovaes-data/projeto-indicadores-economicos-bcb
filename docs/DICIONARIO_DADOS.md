# Dicionário de dados

## Camada `raw` (carregada por `scripts/load_to_neon.py`)

Quatro tabelas com o mesmo formato, uma por série do SGS/Banco Central.

| Coluna | Tipo | Descrição |
|---|---|---|
| `data` | timestamp | Data de referência. **Chave única** (índice `ux_<tabela>_data`). |
| `valor` | double precision | Valor da série na data. |
| `serie` | text | Nome da série (`cambio_dolar`, `ipca`, `selic`, `igpm`). |
| `ingerido_em` | timestamptz | Quando a linha foi inserida ou atualizada pela última vez. |

| Tabela | Série SGS | Unidade | Periodicidade |
|---|---|---|---|
| `raw.cambio_dolar` | 1 | R$ por US$ (venda) | diária |
| `raw.selic` | 432 | Meta Selic, % ao **ano** | diária |
| `raw.ipca` | 433 | variação mensal, % | mensal (dia 1) |
| `raw.igpm` | 189 | variação mensal, % | mensal (dia 1) |

A carga é um *upsert*: linhas que saem da janela de 9,5 anos da API **permanecem** no banco.

## Camada `staging` (views)

| Modelo | Colunas |
|---|---|
| `stg_cambio_dolar` | `data`, `dolar_venda` |
| `stg_selic` | `data`, `meta_selic_aa` (% ao ano) |
| `stg_ipca` | `data`, `ipca_variacao_mensal`, `ipca_acumulado_12m` |
| `stg_igpm` | `data`, `igpm_variacao_mensal` |

`ipca_acumulado_12m` é o acumulado **composto**: `(Π(1 + v/100) − 1) × 100` sobre 12 meses
**consecutivos**. É nulo nos 11 primeiros meses da série e depois de qualquer mês faltante.

## Camada `marts`

`marts.fato_indicadores_economicos`: uma linha por mês (`mes` = dia 1).

| Coluna | Descrição |
|---|---|
| `mes` | Primeiro dia do mês. Chave. |
| `dolar_medio_mes`, `dolar_minimo_mes`, `dolar_maximo_mes` | Estatísticas das cotações de venda do mês (R$/US$). O mês corrente é parcial. |
| `meta_selic_media_mes` | Média da Meta Selic no mês, % ao ano. |
| `ipca_variacao_mensal` | IPCA do mês, %. |
| `ipca_acumulado_12m` | IPCA acumulado composto em 12 meses, %. |
| `igpm_variacao_mensal` | IGP-M do mês, %. |

## `docs/data.json` (consumido pelo dashboard)

```json
{
  "schema_version": 2,
  "updated_at": "18/10/2026 09:00 UTC",
  "updated_at_iso": "2026-10-18T09:00:00Z",
  "dados_ate": {"dolar": "2026-10-17", "selic": "2026-10-17", "ipca": "2026-09-01", "igpm": "2026-09-01"},
  "rows": [{"mes": "2026-09", "dolar_medio_mes": 5.1, "...": "..."}]
}
```

`dados_ate` traz a data do último dado de cada série; o dashboard usa esse campo (e `updated_at_iso`)
para exibir um aviso quando algo estiver desatualizado.
