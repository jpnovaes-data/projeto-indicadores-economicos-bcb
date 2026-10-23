"""Carga no PostgreSQL: idempotência, upsert, atomicidade e migração da tabela legada."""

import pandas as pd
import pytest
from sqlalchemy import event, text

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


def test_upsert_envia_poucos_comandos_insert_e_nenhum_executemany(
    engine_teste, series, tmp_path, monkeypatch
):
    """Regressão de desempenho: cada comando é uma ida e volta à rede.

    Com o banco longe do runner, um INSERT por linha levou minutos em produção.
    """
    monkeypatch.setattr(ld, "LOTE", 300)
    escrever_csvs(tmp_path, series)
    comandos = []

    def contar(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT"):
            comandos.append(executemany)

    event.listen(engine_teste, "before_cursor_execute", contar)
    ld.carregar_serie(engine_teste, "cambio_dolar", tmp_path)  # 700 linhas / lote de 300

    assert len(comandos) == 3  # ceil(700 / 300)
    assert not any(comandos)  # nenhum executemany (que enviaria uma linha por vez)


def test_datas_repetidas_no_csv_nao_quebram_o_upsert(engine_teste, series, tmp_path):
    df = series["ipca"]
    repetida = df.iloc[[3]].assign(valor=9.9)
    escrever_csvs(tmp_path, {"ipca": pd.concat([df, repetida], ignore_index=True)})

    ld.carregar_serie(engine_teste, "ipca", tmp_path)

    (total,) = _q(engine_teste, "select count(*) from raw.ipca")[0]
    assert total == len(df)
    (valor,) = _q(engine_teste, f"select valor from raw.ipca where data = '{df.iloc[3]['data']}'")[
        0
    ]
    assert valor == 9.9  # vale a última ocorrência


def test_migracao_recusa_tabela_legada_com_datas_duplicadas_sem_alterar_nada(
    engine_teste, series, tmp_path
):
    legada = pd.concat([series["ipca"], series["ipca"].iloc[[3, 4]]], ignore_index=True)
    legada.to_sql("ipca", engine_teste, schema="raw", index=False)
    antes = _q(engine_teste, "select data, valor from raw.ipca order by data, valor")
    escrever_csvs(tmp_path, series)

    with pytest.raises(RuntimeError, match="datas duplicadas"):
        ld.carregar_serie(engine_teste, "ipca", tmp_path)

    # a mensagem aponta as datas, e nada mudou: dados iguais, sem coluna nova, sem índice
    assert _q(engine_teste, "select data, valor from raw.ipca order by data, valor") == antes
    colunas = {
        r[0]
        for r in _q(
            engine_teste,
            "select column_name from information_schema.columns "
            "where table_schema='raw' and table_name='ipca'",
        )
    }
    assert "ingerido_em" not in colunas
    assert not _q(engine_teste, "select 1 from pg_indexes where indexname='ux_ipca_data'")
