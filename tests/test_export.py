from datetime import UTC, datetime

import pandas as pd
import pytest

import export_dashboard_data as exp

AGORA = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)


def _mart(**mudancas):
    base = {c: [1.0, 2.0] for c in exp.COLUNAS}
    base["mes"] = ["2026-08-01", "2026-09-01"]
    base.update(mudancas)
    return pd.DataFrame(base)


def test_payload_tem_metadados_e_linhas():
    p = exp.montar_payload(_mart(), {"dolar": "2026-10-17"}, AGORA)
    assert p["schema_version"] == 2
    assert p["updated_at"] == "18/10/2026 09:00 UTC"
    assert p["updated_at_iso"] == "2026-10-18T09:00:00Z"
    assert p["dados_ate"] == {"dolar": "2026-10-17"}
    assert [r["mes"] for r in p["rows"]] == ["2026-08", "2026-09"]


def test_acumulado_do_dbt_passa_sem_mascaramento():
    # a regra dos "12 meses completos" vive no dbt; o export não altera o valor
    p = exp.montar_payload(_mart(ipca_acumulado_12m=[None, 4.4430]), {}, AGORA)
    assert p["rows"][0]["ipca_acumulado_12m"] is None
    assert p["rows"][1]["ipca_acumulado_12m"] == 4.443


def test_arredonda_em_4_casas():
    p = exp.montar_payload(_mart(dolar_medio_mes=[5.123456789, 5.0]), {}, AGORA)
    assert p["rows"][0]["dolar_medio_mes"] == 5.1235


def test_mart_vazio_aborta():
    with pytest.raises(RuntimeError, match="vazio"):
        exp.montar_payload(_mart().iloc[0:0], {}, AGORA)


def test_coluna_ausente_aborta():
    with pytest.raises(RuntimeError, match="ausentes"):
        exp.montar_payload(_mart().drop(columns=["meta_selic_media_mes"]), {}, AGORA)
