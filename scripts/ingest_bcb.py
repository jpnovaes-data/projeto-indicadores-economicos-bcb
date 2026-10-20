"""
Ingestão de séries econômicas do Banco Central do Brasil (SGS).

Fonte: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados

Séries utilizadas:
- 1   -> Dólar comercial (venda), diário
- 433 -> IPCA, variação mensal (%)
- 432 -> Meta Selic, % ao ano, diária
- 189 -> IGP-M, variação mensal (%)

Comportamento em caso de falha: todas as séries são tentadas, mas se QUALQUER
uma falhar o script termina com código de saída 1. Assim o workflow falha
em vez de publicar dados desatualizados em silêncio.
"""

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

SERIES = {
    "cambio_dolar": 1,
    "ipca": 433,
    "selic": 432,
    "igpm": 189,
}

# A API do BCB limita consultas de séries diárias a janelas de 10 anos.
# Usamos 9,5 anos para ficar com margem de segurança.
ANOS_HISTORICO = 9.5

TENTATIVAS = 3
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw"

log = logging.getLogger("ingest_bcb")


def buscar_serie(nome: str, codigo: int, sessao: requests.Session | None = None) -> pd.DataFrame:
    """Busca uma série do SGS (últimos ~9,5 anos) e devolve um DataFrame."""
    sessao = sessao or requests.Session()
    data_final = datetime.now()
    data_inicial = data_final - timedelta(days=int(ANOS_HISTORICO * 365))

    params = {
        "formato": "json",
        "dataInicial": data_inicial.strftime("%d/%m/%Y"),
        "dataFinal": data_final.strftime("%d/%m/%Y"),
    }
    url = BASE_URL.format(codigo=codigo)
    log.info("Buscando série '%s' (código %s)...", nome, codigo)

    resposta = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = sessao.get(url, params=params, timeout=60)
            resposta.raise_for_status()
            break
        except requests.exceptions.RequestException as erro:
            if tentativa == TENTATIVAS:
                raise
            espera = 5 * tentativa
            log.warning(
                "  tentativa %d falhou (%s); nova tentativa em %ds", tentativa, erro, espera
            )
            time.sleep(espera)

    return normalizar(resposta.json(), nome)


def normalizar(dados: list[dict], nome: str) -> pd.DataFrame:
    """Converte o JSON do SGS em DataFrame tipado (data, valor, serie)."""
    df = pd.DataFrame(dados)
    if df.empty or not {"data", "valor"}.issubset(df.columns):
        raise ValueError(f"Resposta vazia ou fora do formato esperado para '{nome}'")

    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df["serie"] = nome
    return df[["data", "valor", "serie"]]


def salvar_csv(df: pd.DataFrame, nome: str, destino: Path = OUTPUT_DIR) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{nome}.csv"
    df.to_csv(caminho, index=False)
    log.info(
        "  -> %d registros (%s a %s) salvos em %s",
        len(df),
        df["data"].min().date(),
        df["data"].max().date(),
        caminho,
    )
    return caminho


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log.info("Iniciando ingestão em %s", datetime.now().isoformat(timespec="seconds"))

    falhas: list[str] = []
    with requests.Session() as sessao:
        for nome, codigo in SERIES.items():
            try:
                salvar_csv(buscar_serie(nome, codigo, sessao), nome)
            except (requests.exceptions.RequestException, ValueError) as erro:
                log.error("  ERRO ao buscar '%s': %s", nome, erro)
                falhas.append(nome)

    if falhas:
        log.error("Ingestão FALHOU para: %s", ", ".join(falhas))
        return 1

    log.info("Ingestão concluída.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
