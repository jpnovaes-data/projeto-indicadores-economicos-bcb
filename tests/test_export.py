from datetime import UTC, datetime

import pandas as pd
import pytest

import export_dashboard_data as exp

AGORA = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)
# último dado de cada série, coerente com os meses de _mart() (2026-08 e 2026-09)
ATE = {"dolar": "2026-09-17", "selic": "2026-09-17", "ipca": "2026-09-01", "igpm": "2026-09-01"}


def _mart(**mudancas):
    base = {c: [1.0, 2.0] for c in exp.COLUNAS}
    base["mes"] = ["2026-08-01", "2026-09-01"]
    base.update(mudancas)
    return pd.DataFrame(base)


def test_payload_tem_metadados_e_linhas():
    p = exp.montar_payload(_mart(), ATE, AGORA)
    assert p["schema_version"] == 2
    assert p["updated_at"] == "18/10/2026 09:00 UTC"
    assert p["updated_at_iso"] == "2026-10-18T09:00:00Z"
    assert p["dados_ate"] == ATE
    assert [r["mes"] for r in p["rows"]] == ["2026-08", "2026-09"]


def test_acumulado_do_dbt_passa_sem_mascaramento():
    # a regra dos "12 meses completos" vive no dbt; o export não altera o valor
    p = exp.montar_payload(_mart(ipca_acumulado_12m=[None, 4.4430]), ATE, AGORA)
    assert p["rows"][0]["ipca_acumulado_12m"] is None
    assert p["rows"][1]["ipca_acumulado_12m"] == 4.443


def test_arredonda_em_4_casas():
    p = exp.montar_payload(_mart(dolar_medio_mes=[5.123456789, 5.0]), ATE, AGORA)
    assert p["rows"][0]["dolar_medio_mes"] == 5.1235


def test_mart_vazio_aborta():
    with pytest.raises(RuntimeError, match="vazio"):
        exp.montar_payload(_mart().iloc[0:0], ATE, AGORA)


def test_coluna_ausente_aborta():
    with pytest.raises(RuntimeError, match="ausentes"):
        exp.montar_payload(_mart().drop(columns=["meta_selic_media_mes"]), ATE, AGORA)


@pytest.mark.parametrize(
    "coluna",
    [
        "ipca_variacao_mensal",
        "igpm_variacao_mensal",
        "meta_selic_media_mes",
        "dolar_medio_mes",
        "dolar_minimo_mes",
        "dolar_maximo_mes",
    ],
)
def test_indicador_totalmente_nulo_impede_a_publicacao(coluna):
    """Regressão: um indicador 100% nulo no mart chegava ao dashboard e quebrava a página."""
    with pytest.raises(RuntimeError, match=f"{coluna}: nenhum valor no mart"):
        exp.montar_payload(_mart(**{coluna: [None, None]}), ATE, AGORA)


def test_mensagem_nomeia_todos_os_indicadores_com_problema():
    mart = _mart(ipca_variacao_mensal=[None, None], igpm_variacao_mensal=[None, None])
    with pytest.raises(RuntimeError) as erro:
        exp.montar_payload(mart, ATE, AGORA)
    assert "ipca_variacao_mensal" in str(erro.value) and "igpm_variacao_mensal" in str(erro.value)


def test_indicador_defasado_em_relacao_a_sua_serie_impede_a_publicacao():
    # a série do IPCA tem dado em 2026-09, mas o mart só o traz até 2026-08
    with pytest.raises(RuntimeError, match="último mês com valor é 2026-08"):
        exp.montar_payload(_mart(ipca_variacao_mensal=[1.0, None]), ATE, AGORA)


def test_dados_ate_incompleto_impede_a_publicacao():
    with pytest.raises(RuntimeError, match="sem a série 'igpm'"):
        exp.montar_payload(_mart(), {k: v for k, v in ATE.items() if k != "igpm"}, AGORA)


def test_nulo_legitimo_no_mes_corrente_de_series_mensais_passa():
    # o mês corrente ainda não tem IPCA nem IGP-M, e a série informa dado só até o mês anterior
    mart = _mart()
    mart.loc[len(mart)] = {**{c: 1.0 for c in exp.COLUNAS}, "mes": "2026-10-01"}
    mart.loc[2, ["ipca_variacao_mensal", "ipca_acumulado_12m", "igpm_variacao_mensal"]] = None
    ate = {**ATE, "dolar": "2026-10-17", "selic": "2026-10-17"}
    assert len(exp.montar_payload(mart, ate, AGORA)["rows"]) == 3
