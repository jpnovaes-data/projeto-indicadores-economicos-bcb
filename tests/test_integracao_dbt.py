"""Pipeline completo (carga -> dbt -> export) contra um PostgreSQL de teste."""

import json

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

import export_dashboard_data as exp
import load_to_neon as ld
from conftest import escrever_csvs, executar_dbt

pytestmark = pytest.mark.integracao


@pytest.fixture
def banco_carregado(engine_teste, series, tmp_path):
    csvs = tmp_path / "csvs"
    escrever_csvs(csvs, series)
    for nome in ld.SERIES:
        ld.carregar_serie(engine_teste, nome, csvs)
    return engine_teste


def _dbt(*args, url, pasta):
    r = executar_dbt(*args, url=url, pasta=pasta)
    return r, r.stdout + r.stderr


def test_pipeline_completo_passa_e_ipca_acumulado_e_composto(banco_carregado, url_teste, tmp_path):
    r, saida = _dbt("run", url=url_teste, pasta=tmp_path)
    assert r.returncode == 0, saida
    r, saida = _dbt("test", url=url_teste, pasta=tmp_path)
    assert r.returncode == 0, saida  # inclui testes unitários, de faixa, frescor e continuidade
    r, saida = _dbt("source", "freshness", url=url_teste, pasta=tmp_path)
    assert r.returncode == 0, saida

    mart = pd.read_sql(
        text("select * from marts.fato_indicadores_economicos order by mes"), banco_carregado
    )
    ipca = mart.dropna(subset=["ipca_variacao_mensal"]).reset_index(drop=True)

    # oráculo independente (pandas/numpy): produto móvel de 12 meses
    esperado = (
        (1 + ipca["ipca_variacao_mensal"] / 100).rolling(12).apply(np.prod, raw=True) - 1
    ) * 100
    assert ipca["ipca_acumulado_12m"].iloc[:11].isna().all()
    np.testing.assert_allclose(
        ipca["ipca_acumulado_12m"].iloc[11:].astype(float), esperado.iloc[11:].round(4), atol=1e-9
    )

    # o mart tem as colunas renomeadas e uma linha por mês, sem buracos
    assert "meta_selic_media_mes" in mart.columns and "selic_media_mes" not in mart.columns
    assert mart["mes"].is_unique


def test_export_gera_json_com_metadados(banco_carregado, url_teste, tmp_path, monkeypatch):
    assert _dbt("run", url=url_teste, pasta=tmp_path)[0].returncode == 0
    saida = tmp_path / "data.json"
    monkeypatch.setattr(exp, "SAIDA", saida)
    monkeypatch.setenv("DATABASE_URL", url_teste)
    assert exp.main() == 0
    dados = json.loads(saida.read_text(encoding="utf-8"))
    assert set(dados["dados_ate"]) == {"dolar", "selic", "ipca", "igpm"}
    assert dados["rows"] and "ipca_acumulado_12m" in dados["rows"][-1]


def test_dbt_test_reprova_quando_falta_um_mes_no_ipca(banco_carregado, url_teste, tmp_path):
    with banco_carregado.begin() as conn:
        conn.execute(
            text(
                "delete from raw.ipca where data = (select data from raw.ipca order by data offset 15 limit 1)"
            )
        )
    assert _dbt("run", url=url_teste, pasta=tmp_path)[0].returncode == 0
    r, saida = _dbt("test", url=url_teste, pasta=tmp_path)
    assert r.returncode != 0 and "serie_mensal_continua" in saida


def test_dbt_test_reprova_quando_o_dolar_esta_parado(banco_carregado, url_teste, tmp_path):
    with banco_carregado.begin() as conn:
        conn.execute(text("delete from raw.cambio_dolar where data > now() - interval '30 days'"))
    assert _dbt("run", url=url_teste, pasta=tmp_path)[0].returncode == 0
    r, saida = _dbt("test", url=url_teste, pasta=tmp_path)
    assert r.returncode != 0 and "frescor_dados" in saida
