import pandas as pd
import pytest
import requests

import ingest_bcb


class RespostaFalsa:
    def __init__(self, dados=None, *, json_invalido=False, status=200, texto=""):
        self._dados, self._invalido = dados, json_invalido
        self.status_code, self.text = status, texto

    def raise_for_status(self):
        pass

    def json(self):
        if self._invalido:
            raise requests.exceptions.JSONDecodeError("Expecting value", "", 0)
        return self._dados


class SessaoFalsa:
    """Devolve, em ordem, cada item da fila: exceção é levantada, resposta é retornada.

    Depois que a fila acaba, repete o último item.
    """

    def __init__(self, *fila):
        self.fila, self.chamadas = list(fila), 0

    def get(self, *_, **__):
        item = self.fila[min(self.chamadas, len(self.fila) - 1)]
        self.chamadas += 1
        if isinstance(item, Exception):
            raise item
        return item


DADOS = [{"data": "01/02/2026", "valor": "0.5"}, {"data": "01/03/2026", "valor": "0.7"}]
BOA = RespostaFalsa(DADOS)
REDE_CAIU = requests.exceptions.ConnectionError("rede caiu")


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(ingest_bcb.time, "sleep", lambda _: None)


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


def test_buscar_serie_tenta_de_novo_e_consegue():
    sessao = SessaoFalsa(REDE_CAIU, REDE_CAIU, BOA)
    df = ingest_bcb.buscar_serie("ipca", 433, sessao)
    assert sessao.chamadas == 3 and len(df) == 2


def test_buscar_serie_desiste_apos_as_tentativas():
    sessao = SessaoFalsa(REDE_CAIU)
    with pytest.raises(requests.exceptions.ConnectionError):
        ingest_bcb.buscar_serie("ipca", 433, sessao)
    assert sessao.chamadas == ingest_bcb.TENTATIVAS


def test_corpo_vazio_com_http_200_e_repetido_e_depois_funciona():
    """Regressão: a API do BCB já respondeu 200 com corpo vazio (JSONDecodeError)."""
    vazio = RespostaFalsa(json_invalido=True, texto="")
    sessao = SessaoFalsa(vazio, vazio, BOA)
    df = ingest_bcb.buscar_serie("selic", 432, sessao)
    assert sessao.chamadas == 3 and len(df) == 2


def test_pagina_html_no_lugar_do_json_tambem_e_repetida():
    html = RespostaFalsa(json_invalido=True, texto="<html>Servico indisponivel</html>")
    sessao = SessaoFalsa(html, BOA)
    assert len(ingest_bcb.buscar_serie("selic", 432, sessao)) == 2
    assert sessao.chamadas == 2


def test_lista_vazia_e_repetida():
    sessao = SessaoFalsa(RespostaFalsa([]), BOA)
    assert len(ingest_bcb.buscar_serie("selic", 432, sessao)) == 2
    assert sessao.chamadas == 2


def test_json_invalido_persistente_falha_depois_de_todas_as_tentativas():
    sessao = SessaoFalsa(RespostaFalsa(json_invalido=True))
    with pytest.raises(ValueError):
        ingest_bcb.buscar_serie("selic", 432, sessao)
    assert sessao.chamadas == ingest_bcb.TENTATIVAS


def test_espera_dobra_a_cada_tentativa(monkeypatch):
    esperas = []
    monkeypatch.setattr(ingest_bcb.time, "sleep", esperas.append)
    with pytest.raises(requests.exceptions.ConnectionError):
        ingest_bcb.buscar_serie("ipca", 433, SessaoFalsa(REDE_CAIU))
    assert esperas == [5, 10, 20]


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


def test_main_trata_json_invalido_como_falha_da_serie(monkeypatch):
    def buscar(nome, codigo, sessao=None):
        if nome == "selic":
            raise requests.exceptions.JSONDecodeError("Expecting value", "", 0)
        return ingest_bcb.normalizar(DADOS, nome)

    monkeypatch.setattr(ingest_bcb, "buscar_serie", buscar)
    monkeypatch.setattr(ingest_bcb, "salvar_csv", lambda *a: None)
    assert ingest_bcb.main() == 1


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
