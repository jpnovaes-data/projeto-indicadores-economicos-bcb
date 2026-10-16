"""
script de ingestao de series economicas do Banco Central do Brasil (SGS).

Fonte: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados

series utilizadas:
- 1   -> Dolar comercial (venda), diario
- 433 -> IPCA, variacao mensal (%)
- 432 -> Meta SELIC, ao dia (%)
- 189 -> IGP-M, variacao mensal (%)
"""

import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

SERIES = {
    "cambio_dolar": 1,
    "ipca": 433,
    "selic": 432,
    "igpm": 189,
}

# A API do BCB limita as consultas de series diarias a uma janela de 10 anos.
# Usamos 9 anos e meio para ficar com margem de seguranca.
ANOS_HISTORICO = 9.5

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw"


def buscar_serie(nome: str, codigo: int) -> pd.DataFrame:
    """Busca uma serie do SGS (ultimos ~10 anos) e retorna como DataFrame."""
    data_final = datetime.now()
    data_inicial = data_final - timedelta(days=int(ANOS_HISTORICO * 365))

    params = {
        "formato": "json",
        "dataInicial": data_inicial.strftime("%d/%m/%Y"),
        "dataFinal": data_final.strftime("%d/%m/%Y"),
    }

    url = BASE_URL.format(codigo=codigo)
    print(f"Buscando serie '{nome}' (codigo {codigo})...")

    tentativas = 3
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = requests.get(url, params=params, timeout=60)
            resposta.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if tentativa == tentativas:
                raise
            espera = 5 * tentativa
            print(f"  tentativa {tentativa} falhou ({e}), "
                  f"tentando de novo em {espera}s...")
            time.sleep(espera)

    dados = resposta.json()
    df = pd.DataFrame(dados)

    # A API retorna data como string "dd/mm/aaaa" e valor como string
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df["serie"] = nome

    print(f"  -> {len(df)} registros encontrados "
          f"({df['data'].min().date()} a {df['data'].max().date()})")

    return df[["data", "valor", "serie"]]


def salvar_csv(df: pd.DataFrame, nome: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    caminho = OUTPUT_DIR / f"{nome}.csv"
    df.to_csv(caminho, index=False)
    print(f"  -> salvo em {caminho}")


def main():
    print(f"Iniciando ingestao em {datetime.now().isoformat()}\n")

    for nome, codigo in SERIES.items():
        try:
            df = buscar_serie(nome, codigo)
            salvar_csv(df, nome)
        except requests.exceptions.RequestException as e:
            print(f"  ERRO ao buscar '{nome}': {e}")
        print()

    print("Ingestao concluida.")


if __name__ == "__main__":
    main()