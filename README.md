# Indicadores Econômicos do Brasil: pipeline de dados ponta a ponta

[![Pipeline diário](https://github.com/jpnovaes-data/projeto-indicadores-economicos-bcb/actions/workflows/pipeline_diario.yml/badge.svg)](https://github.com/jpnovaes-data/projeto-indicadores-economicos-bcb/actions/workflows/pipeline_diario.yml)
[![Python CI](https://github.com/jpnovaes-data/projeto-indicadores-economicos-bcb/actions/workflows/ci_python.yml/badge.svg)](https://github.com/jpnovaes-data/projeto-indicadores-economicos-bcb/actions/workflows/ci_python.yml)
[![Terraform CI](https://github.com/jpnovaes-data/projeto-indicadores-economicos-bcb/actions/workflows/terraform_ci.yml/badge.svg)](https://github.com/jpnovaes-data/projeto-indicadores-economicos-bcb/actions/workflows/terraform_ci.yml)
[![Terraform Plan](https://github.com/jpnovaes-data/projeto-indicadores-economicos-bcb/actions/workflows/terraform_plan.yml/badge.svg)](https://github.com/jpnovaes-data/projeto-indicadores-economicos-bcb/actions/workflows/terraform_plan.yml)

Pipeline automatizado que coleta indicadores econômicos da API SGS do Banco Central do Brasil, valida e carrega os dados em um PostgreSQL na nuvem, transforma e testa os modelos com dbt e publica um dashboard no GitHub Pages. Tudo roda sozinho todos os dias às 06h (horário de Brasília) via GitHub Actions, e **avisa quando falha**.

A infraestrutura do banco é gerenciada como código com Terraform (projeto Neon), com o state armazenado remotamente no HCP Terraform.

**Dashboard ao vivo:** https://jpnovaes-data.github.io/projeto-indicadores-economicos-bcb/

![Dashboard](docs/dashboard.png)

## Arquitetura

```mermaid
flowchart LR
    A["API SGS<br/>Banco Central"] --> B["Python<br/>ingest_bcb.py"]
    B --> C["CSV<br/>data/raw"]
    C --> V{"validacao.py<br/>(gate)"}
    V -- aprovado --> D["load_to_neon.py<br/>upsert transacional"]
    V -- reprovado --> X["pipeline falha<br/>banco intacto"]
    D --> E[("Neon PostgreSQL<br/>schema raw")]
    E --> F["dbt<br/>staging (views)"]
    F --> G["dbt<br/>marts (tabela)"]
    G --> H["export_dashboard_data.py<br/>docs/data.json"]
    H --> I["GitHub Pages<br/>dashboard"]
    J["Terraform"] -. "gerencia" .-> E
    J -. "state em" .-> L["HCP Terraform"]
    K["GitHub Actions<br/>cron diário"] -. "orquestra" .-> B
    K -. "falha vira issue" .-> N["Alerta"]
```

O pipeline diário de dados **não executa `terraform apply`**. Mudanças de infraestrutura são planejadas, revisadas e aplicadas separadamente.

## Stack

| Camada | Tecnologia |
|---|---|
| Fonte dos dados | API SGS do Banco Central do Brasil |
| Ingestão e carga | Python (requests, pandas, SQLAlchemy) |
| Banco de dados | PostgreSQL 17 no Neon (região São Paulo) |
| Infraestrutura como código | Terraform (provider kislerdm/neon) |
| State do Terraform | HCP Terraform (plano gratuito) |
| Transformação e testes | dbt-core e dbt-postgres |
| Qualidade de código | pytest, ruff, pre-commit (gitleaks) |
| Orquestração, CI e deploy | GitHub Actions |
| Visualização | HTML, JavaScript e Chart.js no GitHub Pages |

## Fontes de dados

API pública, sem necessidade de chave de acesso.

| Indicador | Código SGS | Periodicidade |
|---|---|---|
| Dólar comercial (venda) | 1 | Diária |
| IPCA, variação mensal (%) | 433 | Mensal |
| Meta Selic (% ao ano) | 432 | Diária |
| IGP-M, variação mensal (%) | 189 | Mensal |

A API limita séries diárias a janelas de 10 anos, então a ingestão busca os últimos 9,5 anos. Como a carga é um upsert, o histórico que sai dessa janela **permanece** no banco.

## Como o pipeline funciona

1. **Ingestão** (`scripts/ingest_bcb.py`): consulta as 4 séries, trata tipos e datas e salva em CSV, com até 4 tentativas e espera crescente (5, 10 e 20 s). As tentativas cobrem também respostas ruins da API, como HTTP 200 com corpo vazio ou HTML. Tenta todas as séries, mas **termina com erro se qualquer uma falhar**, para o workflow nunca ficar "verde" com dados velhos.
2. **Validação** (`scripts/validacao.py`): antes de tocar o banco, confere se cada arquivo é legível, número mínimo de linhas, datas válidas e únicas, **nenhum valor nulo ou não numérico**, faixa plausível dos valores, rótulo da coluna `serie` e idade do último dado. Se reprovar, a carga é abortada e o banco permanece como estava.
3. **Carga** (`scripts/load_to_neon.py`): *upsert* (`INSERT ... ON CONFLICT`) em **uma transação por série**, enviado em lotes de 1.000 linhas (poucas idas e voltas à rede, já que o runner fica longe do banco). Nunca esvazia a tabela: se algo falhar no meio, o rollback preserva os dados anteriores. Rodar duas vezes não duplica nada, e a coluna `ingerido_em` registra quando cada linha foi gravada.
4. **Transformação** (`dbt_economia/`): 4 views em `staging` e a tabela `marts.fato_indicadores_economicos`.
5. **Qualidade**: `dbt source freshness` e **37 testes dbt** (34 de dados e 3 unitários), descritos abaixo. Se algum falhar, o workflow falha e o dashboard não é republicado.
6. **Exportação** (`scripts/export_dashboard_data.py`): gera `docs/data.json` com as linhas mensais e metadados (data do último dado de cada série). **Recusa gerar o arquivo** se algum indicador estiver sem valores ou atrás da data do último dado da sua série, e o dashboard não é publicado.
7. **Publicação**: o job de deploy envia `docs/` ao GitHub Pages, somente se o job anterior passar.
8. **Alerta**: se o pipeline ou o deploy falharem, um job abre (ou comenta em) uma issue com o rótulo `pipeline-falhou`; opcionalmente também chama um webhook compatível com Slack.

### Modelo de dados

```
raw.cambio_dolar | raw.ipca | raw.selic | raw.igpm            (upsert, chave única em "data")
        |
staging.stg_cambio_dolar | stg_ipca | stg_selic | stg_igpm      (views)
        |
marts.fato_indicadores_economicos                               (tabela, 1 linha por mês)
```

Dólar e Meta Selic (diários) viram média, mínimo e máximo do mês (a Selic, só a média). IPCA e IGP-M (mensais) entram direto. Veja o [dicionário de dados](docs/DICIONARIO_DADOS.md).

### Testes de qualidade (dbt)

| Tipo | O que verifica |
|---|---|
| `unique` / `not_null` | chaves de data nas views e `mes` no mart |
| `valor_na_faixa` (genérico) | valores plausíveis: dólar 0,5 a 15; Selic 0 a 60; IPCA e IGP-M -5 a 10; IPCA 12m -5 a 40 |
| `serie_mensal_continua` (genérico) | IPCA e IGP-M sem mês faltando |
| `frescor_dados` | último dado de cada série dentro da tolerância (10 dias para diárias, 80 para mensais) |
| `meses_continuos_no_mart` | tabela fato sem buracos entre meses |
| `mart_preenche_todos_os_indicadores` | todo mês com dado de um indicador no staging está **preenchido** no mart (um indicador 100% nulo falha) |
| `serie_diaria_sem_buracos` (genérico) | dólar sem intervalo maior que 7 dias (só dias úteis; o maior real foi 5) e Selic sem nenhum dia faltando |
| `dolar_minimo_medio_maximo` | mínimo ≤ média ≤ máximo |
| **testes unitários dbt** | IPCA composto (12 × 1,00% = 12,6825%, e não 12%), acumulado nulo quando há buraco, renomeação da Selic |
| `source freshness` | a carga rodou nas últimas horas (`ingerido_em`) |

### Por que o IPCA acumulado é composto

O acumulado de 12 meses é o produto das taxas, não a soma: `(Π(1 + v/100) − 1) × 100`. Nos dados do projeto, a soma simples (usada antes) se afastava do valor correto em média 0,14 p.p., com picos de 0,62 p.p. O cálculo agora vive no dbt (`stg_ipca`) e foi conferido contra um cálculo independente em pandas, com diferença zero.

## Infraestrutura como código

O projeto Neon foi criado pelo console e depois **importado** para o Terraform. O primeiro `plan` propôs destruir e recriar o recurso por divergências em `pg_version` e `region_id`, então o código foi ajustado para refletir a realidade antes de qualquer `apply`. Hoje o plano retorna `No changes`.

- **State remoto** no HCP Terraform (workspace `projeto-economia`, execução local), em vez de um arquivo só no computador.
- **`prevent_destroy = true`** no recurso do banco, que transforma qualquer plano destrutivo em erro.
- Procedimentos de plano, importação, destruição e recuperação em [`terraform/README.md`](terraform/README.md).

## CI/CD

| Workflow | Quando roda | O que faz |
|---|---|---|
| `pipeline_diario.yml` | Diário às 06h (Brasília) e manual | Ingestão, validação, carga, dbt (freshness, run, test), exportação, deploy e alerta de falha |
| `ci_python.yml` | Todo pull request e push na `main` | `ruff` e `pytest` (unitários + integração com Postgres e dbt em container) |
| `terraform_ci.yml` | Mudanças em `terraform/` | `fmt -check`, `init -backend=false` e `validate`, sem credenciais |
| `terraform_plan.yml` | Todo pull request e manual | Detecta se `terraform/` mudou: se sim, faz o plano contra o state remoto (somente leitura); se não, termina em segundos sem usar secrets. Sempre reporta status, então pode ser check obrigatório. Pulado para Dependabot e forks |

Boas práticas aplicadas: **actions fixadas por SHA** do commit (o Dependabot mantém atualizado), **permissões mínimas** por job (`pages: write` só no deploy, `issues: write` só no alerta), `persist-credentials: false`, `timeout-minutes` em todos os jobs e **um único secret de banco** (`DATABASE_URL`; o profile do dbt é derivado dele). Nenhum workflow aplica mudanças na infraestrutura.

## Segurança

Credenciais ficam em GitHub Secrets e em arquivos locais fora do Git, e o dashboard lê apenas um JSON estático, sem conexão com o banco. O state do Terraform é tratado como informação sensível. O hook `gitleaks` do pre-commit barra segredos antes do commit. Detalhes, incluindo configurações recomendadas do GitHub e o que fazer se um segredo vazar, em [`SECURITY.md`](SECURITY.md). O Dependabot abre PRs semanais (minor/patch agrupados).

## Dashboard

Painel no estilo de terminais financeiros, com tema claro e escuro automático:

- Cartões de KPI (dólar, Meta Selic, IPCA acumulado em 12 meses e IGP-M) com variação contra o mês anterior e sparkline dos últimos 24 meses.
- Selo de "mês parcial" para séries diárias quando o mês corrente ainda não fechou.
- **Aviso de dados desatualizados**: um banner aparece se o pipeline parar de rodar (mais de 3 dias) ou se alguma série ficar além da tolerância da sua periodicidade.
- Seletor de período (1A, 3A, 5A, Máx) para os gráficos de dólar com mínimo e máximo, Meta Selic, IPCA mensal e acumulado e IGP-M.

Cada KPI mostra o último mês com dado daquela série, já que os indicadores são divulgados em ritmos diferentes.

### Por que GitHub Pages e não Power BI

- **Acesso imediato:** quem abre o link vê os dados, sem login, licença ou instalação.
- **Automação completa:** o dashboard é atualizado pelo mesmo pipeline que gera os dados.
- **Tudo versionado:** a página é código e pode ser revisada no Git, ao contrário de um `.pbix` binário.
- **Sem credenciais no navegador:** a página lê apenas `data.json`.

A camada `marts` continua pronta para ser consumida por Power BI ou outra ferramenta de BI.

## Decisões técnicas e aprendizados

- **De `DROP` a `TRUNCATE` a `UPSERT`:** o `if_exists="replace"` do pandas derrubava as tabelas e o Postgres bloqueava, porque as views do dbt dependem delas. O `TRUNCATE` corrigiu isso, mas rodava em transação separada da inserção: uma falha no meio deixava a tabela **vazia**. O upsert numa única transação elimina esse risco (há teste de integração que injeta o erro e confere o rollback).
- **Falhar alto em vez de publicar dados velhos:** ingestão e carga agora saem com erro, e o dashboard avisa sozinho quando os dados envelhecem.
- **Um teste só vale se detecta o problema:** ao injetar falhas de propósito, descobri que um mês faltando no IPCA passava despercebido (o mart junta as 4 séries, então o mês continuava existindo graças ao dólar). Isso gerou o teste `serie_mensal_continua`.
- **Teste que não pode falhar é pior que nenhum:** uma auditoria externa apontou que meu teste do mart era verdadeiro por construção. Comprovei quebrando o mart de propósito: com o IPCA 100% nulo, os 35 testes dbt e o teste de integração passavam. Troquei por um teste que compara cada indicador do mart com o staging e refiz a quebra: agora falha. Também havia uma comparação que passava com os dois lados vazios, e agora ela exige dados antes de comparar.
- **Regra de negócio no dbt, não no script de exportação:** o acumulado de 12 meses era "mascarado" no Python; agora vem pronto e testado do modelo.
- **Importar, não recriar:** preserva os dados e evita destruir o banco.
- **State remoto e proteção contra destruição:** reduzem o risco de perder o controle do recurso ou apagá-lo por engano.
- **Segredos fora do Git:** `.env`, state e arquivos de plano estão no `.gitignore`, e o histórico foi varrido sem achados.

## Limitações e próximos passos

- A ingestão ainda busca toda a janela de 9,5 anos a cada execução (são só 4 requisições); a carga no banco, porém, já é incremental. Um próximo passo é buscar só os dias novos.
- Actions fixadas nas versões *major* atualmente em uso; os PRs do Dependabot para majors novos devem ser revisados um a um.
- O Chart.js é carregado de CDN com versão fixa, mas sem verificação SRI.
- Não há ambiente de homologação provisionado via Terraform; o suporte a `dev`/`prod` existe nos scripts e no profile do dbt (ver abaixo), mas a branch de dev do Neon é criada manualmente.
- Proteção da branch `main` e demais configurações do GitHub são manuais (veja `SECURITY.md`).

## Como executar localmente

Pré-requisitos: Python 3.13, um PostgreSQL acessível (por exemplo, um projeto gratuito no Neon) e Terraform 1.15 ou superior para a infraestrutura.

```bash
pip install -r requirements-dev.txt
cp .env.example .env          # preencha DATABASE_URL (nunca commitar o .env)

make run                       # ingestão, validação, carga, dbt e exportação do dashboard
make serve                     # http://localhost:8000
```

Sem `make` (ex.: Windows puro), os comandos equivalentes são:

```bash
python scripts/ingest_bcb.py
python scripts/validacao.py
python scripts/load_to_neon.py
python scripts/gerar_profile_dbt.py          # escreve ~/.dbt/profiles.yml a partir do .env
cd dbt_economia && dbt source freshness && dbt run && dbt test && cd ..
python scripts/export_dashboard_data.py
python -m http.server --directory docs 8000
```

### Ambiente de desenvolvimento (opcional)

Crie uma **branch** no Neon (gratuito), defina `DATABASE_URL_DEV` no `.env` e rode `python scripts/gerar_profile_dbt.py`: o target padrão local passa a ser `dev`, e a produção só é tocada com `--target prod`. O CI usa sempre `prod`.

### Testes

```bash
make lint                      # ruff
make test                      # 58 testes unitários, sem banco
# integração: exige um banco DESCARTÁVEL cujo nome contenha "test"
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/economia_test?sslmode=disable
make test-integracao           # 17 testes: carga, migração, rollback, desempenho, dbt e export
```

Os testes de integração se recusam a rodar contra qualquer banco cujo nome não contenha `test`, pois eles recriam os schemas. Para ativar os hooks locais: `pre-commit install`.

Para o Terraform, siga o [runbook](terraform/README.md). Para o deploy, cadastre o secret `DATABASE_URL` e, em **Settings, Pages**, selecione **GitHub Actions** como fonte.

## Estrutura do repositório

```
.
├── .github/
│   ├── dependabot.yml
│   └── workflows/
│       ├── pipeline_diario.yml
│       ├── ci_python.yml
│       ├── terraform_ci.yml
│       └── terraform_plan.yml
├── scripts/
│   ├── ingest_bcb.py            # API SGS -> CSV (falha alto)
│   ├── validacao.py             # gate de qualidade antes da carga
│   ├── load_to_neon.py          # upsert transacional
│   ├── gerar_profile_dbt.py     # profiles.yml a partir de DATABASE_URL
│   └── export_dashboard_data.py
├── dbt_economia/
│   ├── models/staging/          # views + testes unitários
│   ├── models/marts/
│   ├── tests/                   # testes singulares e genéricos
│   ├── macros/
│   └── profiles.yml.example
├── tests/                       # pytest: unitários e integração
├── terraform/
├── docs/
│   ├── index.html               # data.json é gerado no CI e não é versionado
│   └── DICIONARIO_DADOS.md
├── Makefile
├── pyproject.toml               # ruff e pytest
├── .pre-commit-config.yaml
├── requirements.txt             # versões fixadas
├── requirements-dev.txt
├── SECURITY.md
└── .env.example
```

## Autor

João Pedro Novaes, Analista de Dados.
[LinkedIn](https://www.linkedin.com/in/jpedro-novaes)
