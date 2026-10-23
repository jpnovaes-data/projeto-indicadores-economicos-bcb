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


def test_valores_nulos_parciais_sao_reprovados():
    """Regressão: 300 nulos em 1.600 linhas passavam, pois só se reprovava série 100% nula."""
    df = _df([5.0] * 1600)
    df.loc[df.index[100:400], "valor"] = float("nan")
    problemas = validacao.validar_dataframe("cambio_dolar", df, HOJE)
    assert any("300 valores nulos ou não numéricos" in p for p in problemas)


def test_um_unico_valor_nulo_ja_e_reprovado():
    df = _df([5.0] * 1600)
    df.loc[10, "valor"] = float("nan")
    assert any(
        "1 valores nulos" in p for p in validacao.validar_dataframe("cambio_dolar", df, HOJE)
    )


def test_valor_nao_numerico_e_reprovado_sem_quebrar():
    df = _df([5.0] * 1600).astype({"valor": object})
    df.loc[3, "valor"] = "abc"
    problemas = validacao.validar_dataframe("cambio_dolar", df, HOJE)
    assert any("1 valores nulos ou não numéricos" in p for p in problemas)


def test_datas_invalidas_sao_reprovadas_sem_quebrar():
    df = _df([5.0] * 1600).astype({"data": object})
    df.loc[2, "data"] = "31/02/2026"
    problemas = validacao.validar_dataframe("cambio_dolar", df, HOJE)
    assert any("1 datas nulas ou inválidas" in p for p in problemas)


def test_rotulo_de_serie_trocado_e_reprovado():
    df = _df([5.0] * 1600, nome="selic")  # dados de "selic" dentro do arquivo do dólar
    problemas = validacao.validar_dataframe("cambio_dolar", df, HOJE)
    assert any("coluna 'serie'" in p for p in problemas)


def test_rotulo_de_serie_vazio_e_reprovado():
    df = _df([5.0] * 1600)
    df.loc[0, "serie"] = None
    assert any("coluna 'serie'" in p for p in validacao.validar_dataframe("cambio_dolar", df, HOJE))


def test_csv_vazio_vira_erro_de_validacao_padronizado(tmp_path):
    for nome in validacao.REGRAS:
        (tmp_path / f"{nome}.csv").write_text("")
    with pytest.raises(validacao.ErroValidacao, match="ilegível ou vazio"):
        validacao.validar_diretorio(tmp_path, HOJE)


def test_csv_malformado_vira_erro_de_validacao_padronizado(tmp_path):
    for nome in validacao.REGRAS:
        (tmp_path / f"{nome}.csv").write_text(
            "data,valor,serie\n2026-01-01,1.0\n2026-01-02,2.0,x,y\n"
        )
    with pytest.raises(validacao.ErroValidacao, match="ilegível ou vazio"):
        validacao.validar_diretorio(tmp_path, HOJE)
