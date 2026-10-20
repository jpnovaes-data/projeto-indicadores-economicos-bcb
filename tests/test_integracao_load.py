"""Carga no PostgreSQL: idempotência, upsert, atomicidade e migração da tabela legada."""

import pandas as pd
import pytest
from sqlalchemy import text

import load_to_neon as ld
from conftest import escrever_csvs

pytestmark = pytest.mark.integracao


def _q(engine, sql):
    with engine.connect() as conn:
        return conn.execute(text(sql)).fetchall()


def test_cria_tabela_com_indice_unico_e_ingerido_em(engine_teste, series, tmp_path):
    escrever_csvs(tmp_path, series)
    ld.carregar_serie(engine_teste, "ipca", tmp_path)
    colunas = {
        r[0]
        for r in _q(
            engine_teste,
            "select column_name from information_schema.columns "
            "where table_schema='raw' and table_name='ipca'",
        )
    }
    assert {"data", "valor", "serie", "ingerido_em"} <= colunas
    assert _q(
        engine_teste, "select 1 from pg_indexes where schemaname='raw' and indexname='ux_ipca_data'"
    )


def test_carga_e_idempotente(engine_teste, series, tmp_path):
    escrever_csvs(tmp_path, series)
    for _ in range(3):
        ld.carregar_serie(engine_teste, "ipca", tmp_path)
    (total,) = _q(engine_teste, "select count(*) from raw.ipca")[0]
    assert total == len(series["ipca"])


def test_upsert_atualiza_valor_e_preserva_historico_fora_da_janela(engine_teste, series, tmp_path):
    escrever_csvs(tmp_path, series)
    ld.carregar_serie(engine_teste, "ipca", tmp_path)

    # segunda carga: janela menor (perdeu os 10 primeiros meses) e um valor revisado
    nova = series["ipca"].iloc[10:].copy()
    nova.iloc[-1, nova.columns.get_loc("valor")] = 9.99
    escrever_csvs(tmp_path, {"ipca": nova})
    ld.carregar_serie(engine_teste, "ipca", tmp_path)

    (total,) = _q(engine_teste, "select count(*) from raw.ipca")[0]
    assert total == len(series["ipca"])  # histórico antigo foi mantido
    (ultimo,) = _q(engine_teste, "select valor from raw.ipca order by data desc limit 1")[0]
    assert ultimo == 9.99  # valor revisado foi atualizado


def test_falha_no_meio_da_carga_preserva_os_dados_antigos(engine_teste, series, tmp_path):
    escrever_csvs(tmp_path, series)
    ld.carregar_serie(engine_teste, "ipca", tmp_path)
    antes = _q(engine_teste, "select data, valor from raw.ipca order by data")

    corrompido = series["ipca"].copy().astype({"valor": object})
    corrompido.iloc[5, corrompido.columns.get_loc("valor")] = "abc"  # quebra no meio do INSERT
    corrompido.iloc[0, corrompido.columns.get_loc("valor")] = 7.77  # linha anterior à quebra
    escrever_csvs(tmp_path, {"ipca": corrompido})
    with pytest.raises(Exception):  # noqa: B017 - qualquer erro de banco serve
        ld.carregar_serie(engine_teste, "ipca", tmp_path)

    # rollback completo: nem a linha "boa" 7.77 entrou, e nada foi apagado
    assert _q(engine_teste, "select data, valor from raw.ipca order by data") == antes


def test_migra_tabela_legada_criada_pelo_pandas(engine_teste, series, tmp_path):
    # estado de produção ANTES desta versão: sem ingerido_em e sem chave única
    series["ipca"].to_sql("ipca", engine_teste, schema="raw", index=False)
    assert "ingerido_em" not in {
        r[0]
        for r in _q(
            engine_teste,
            "select column_name from information_schema.columns "
            "where table_schema='raw' and table_name='ipca'",
        )
    }

    escrever_csvs(tmp_path, series)
    ld.carregar_serie(engine_teste, "ipca", tmp_path)

    (total, distintas) = _q(engine_teste, "select count(*), count(distinct data) from raw.ipca")[0]
    assert total == distintas == len(series["ipca"])
    assert _q(engine_teste, "select count(ingerido_em) from raw.ipca")[0][0] == total


def test_main_aborta_sem_tocar_no_banco_quando_a_validacao_falha(
    engine_teste, monkeypatch, tmp_path
):
    escrever_csvs(tmp_path, {"ipca": pd.DataFrame({"data": [], "valor": [], "serie": []})})
    monkeypatch.setattr(
        ld,
        "validar_diretorio",
        lambda *a, **k: (_ for _ in ()).throw(ld.ErroValidacao("reprovado")),
    )
    monkeypatch.setattr(ld, "conectar", lambda: pytest.fail("não deveria conectar ao banco"))
    assert ld.main([]) == 1
