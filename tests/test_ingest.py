import pandas as pd
import pytest
import requests

import ingest_bcb


class RespostaFalsa:
    def __init__(self, dados):
        self._dados = dados

    def raise_for_status(self):
        pass

    def json(self):
        return self._dados


class SessaoFalsa:
    """Falha `falhas` vezes e depois responde com sucesso."""

    def __init__(self, dados, falhas=0):
        self.dados, self.falhas, self.chamadas = dados, falhas, 0

    def get(self, *_, **__):
        self.chamadas += 1
        if self.chamadas <= self.falhas:
            raise requests.exceptions.ConnectionError("rede caiu")
        return RespostaFalsa(self.dados)


DADOS = [
    {"data": "01/02/2026", "valor": "0,5".replace(",", ".")},
    {"data": "01/03/2026", "valor": "0.7"},
]


def test_normalizar_converte_tipos():
    df = ingest_bcb.normalizar(DADOS, "ipca")
    assert list(df.columns) == ["data", "valor", "serie"]
    assert df["data"].iloc[0] == pd.Timestamp("2026-02-01")
    assert df["valor"].tolist() == [0.5, 0.7]
    assert set(df["serie"]) == {"ipca"}


def test_normalizar_valor_invalido_vira_nan():
    df = ingest_bcb.normalizar([{"data": "01/02/2026", "valor": ""}], "ipca")
    assert pd.isna(df["valor"].iloc[0])


@pytest.mark.parametrize("dados", [[], [{"x": 1}]])
def test_normalizar_rejeita_resposta_fora_do_formato(dados):
    with pytest.raises(ValueError):
        ingest_bcb.normalizar(dados, "ipca")


def test_buscar_serie_tenta_de_novo_e_consegue(monkeypatch):
    monkeypatch.setattr(ingest_bcb.time, "sleep", lambda _: None)
    sessao = SessaoFalsa(DADOS, falhas=2)
    df = ingest_bcb.buscar_serie("ipca", 433, sessao)
    assert sessao.chamadas == 3 and len(df) == 2


def test_buscar_serie_desiste_apos_as_tentativas(monkeypatch):
    monkeypatch.setattr(ingest_bcb.time, "sleep", lambda _: None)
    sessao = SessaoFalsa(DADOS, falhas=99)
    with pytest.raises(requests.exceptions.ConnectionError):
        ingest_bcb.buscar_serie("ipca", 433, sessao)
    assert sessao.chamadas == ingest_bcb.TENTATIVAS


def test_main_falha_com_codigo_1_se_qualquer_serie_falhar(monkeypatch):
    def buscar(nome, codigo, sessao=None):
        if nome == "ipca":
            raise requests.exceptions.Timeout("lento demais")
        return ingest_bcb.normalizar(DADOS, nome)

    salvos = []
    monkeypatch.setattr(ingest_bcb, "buscar_serie", buscar)
    monkeypatch.setattr(ingest_bcb, "salvar_csv", lambda df, nome, *a: salvos.append(nome))
    assert ingest_bcb.main() == 1
    assert "ipca" not in salvos and len(salvos) == 3  # as demais ainda foram tentadas


def test_main_retorna_0_quando_tudo_funciona(monkeypatch):
    monkeypatch.setattr(
        ingest_bcb, "buscar_serie", lambda n, c, s=None: ingest_bcb.normalizar(DADOS, n)
    )
    monkeypatch.setattr(ingest_bcb, "salvar_csv", lambda *a: None)
    assert ingest_bcb.main() == 0


def test_salvar_csv_grava_arquivo(tmp_path):
    df = ingest_bcb.normalizar(DADOS, "ipca")
    caminho = ingest_bcb.salvar_csv(df, "ipca", tmp_path)
    assert pd.read_csv(caminho).shape == (2, 3)
