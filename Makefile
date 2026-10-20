# Atalhos de desenvolvimento. No Windows, use Git Bash/WSL ou rode os comandos à mão.
PY ?= python
DBT = cd dbt_economia && dbt

.PHONY: install ingest validar load dbt dashboard run lint format test test-integracao serve

install:            ## instala dependências de desenvolvimento
	$(PY) -m pip install -r requirements-dev.txt

ingest:             ## busca as séries no Banco Central
	$(PY) scripts/ingest_bcb.py

validar:            ## valida os CSVs brutos antes da carga
	$(PY) scripts/validacao.py

load:               ## carga (upsert) no PostgreSQL
	$(PY) scripts/load_to_neon.py

dbt:                ## profile + frescor + run + test
	$(PY) scripts/gerar_profile_dbt.py
	$(DBT) source freshness
	$(DBT) run
	$(DBT) test

dashboard:          ## gera docs/data.json
	$(PY) scripts/export_dashboard_data.py

run: ingest validar load dbt dashboard   ## pipeline completo

serve:              ## dashboard em http://localhost:8000
	$(PY) -m http.server --directory docs 8000

lint:               ## ruff (sem alterar arquivos)
	ruff check . && ruff format --check .

format:             ## corrige estilo
	ruff check --fix . && ruff format .

test:               ## testes unitários (não precisam de banco)
	pytest -m "not integracao"

test-integracao:    ## exige TEST_DATABASE_URL apontando para um banco de TESTE
	pytest -m integracao
