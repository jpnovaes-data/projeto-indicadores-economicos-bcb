from datetime import date

import pandas as pd
import pytest

import validacao
from conftest import escrever_csvs, series_sinteticas

HOJE = date.today()


def test_series_sinteticas_passam(tmp_path):
    escrever_csvs(tmp_path, series_sinteticas())
    # min_linhas das regras reais é maior que o das fixtures: relaxa só para este teste
    regras = {k: {**v, "min_linhas": 10} for k, v in validacao.REGRAS.items()}
    original = validacao.REGRAS
    validacao.REGRAS = regras
    try:
        validacao.validar_diretorio(tmp_path, HOJE)
    finally:
        validacao.REGRAS = original


def _df(valores, fim=None, nome="cambio_dolar"):
    fim = fim or pd.Timestamp(HOJE)
    datas = pd.date_range(end=fim, periods=len(valores), freq="D")
    return pd.DataFrame({"data": datas, "valor": valores, "serie": nome})


def test_poucas_linhas_e_reprovado():
    problemas = validacao.validar_dataframe("cambio_dolar", _df([5.0] * 10), HOJE)
    assert any("apenas 10 linhas" in p for p in problemas)


def test_valor_fora_da_faixa_e_reprovado():
    df = _df([5.0] * 1600)
    df.loc[5, "valor"] = 5000.0  # erro de escala
    assert any("fora da faixa" in p for p in validacao.validar_dataframe("cambio_dolar", df, HOJE))


def test_dados_velhos_sao_reprovados():
    df = _df([5.0] * 1600, fim=pd.Timestamp(HOJE) - pd.Timedelta(days=40))
    assert any("último dado" in p for p in validacao.validar_dataframe("cambio_dolar", df, HOJE))


def test_datas_duplicadas_sao_reprovadas():
    df = _df([5.0] * 1600)
    df.loc[1, "data"] = df.loc[0, "data"]
    assert any("duplicadas" in p for p in validacao.validar_dataframe("cambio_dolar", df, HOJE))


def test_colunas_erradas_sao_reprovadas():
    df = pd.DataFrame({"a": [1]})
    assert "colunas esperadas" in validacao.validar_dataframe("ipca", df, HOJE)[0]


def test_serie_saudavel_nao_tem_problemas():
    assert validacao.validar_dataframe("cambio_dolar", _df([5.0] * 1600), HOJE) == []


def test_arquivo_ausente_e_reprovado(tmp_path):
    with pytest.raises(validacao.ErroValidacao, match="não encontrado"):
        validacao.validar_diretorio(tmp_path, HOJE)
