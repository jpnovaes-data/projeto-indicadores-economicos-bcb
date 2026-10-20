"""
Validação dos CSVs brutos ANTES de tocar o banco.

Se qualquer verificação falhar, a carga é abortada e o banco continua com os
dados anteriores (que são consistentes). Também pode ser executado sozinho:

    python scripts/validacao.py
"""

import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

# Regras por série:
#   min_linhas   -> abaixo disso consideramos a carga parcial
#   max_atraso   -> idade máxima (dias) tolerada para o último ponto
#   faixa        -> limites plausíveis do valor (detecta unidade/escala errada)
REGRAS = {
    "cambio_dolar": {"min_linhas": 1500, "max_atraso": 10, "faixa": (0.5, 15.0)},
    "selic": {"min_linhas": 2500, "max_atraso": 10, "faixa": (0.0, 60.0)},
    "ipca": {"min_linhas": 100, "max_atraso": 80, "faixa": (-5.0, 10.0)},
    "igpm": {"min_linhas": 100, "max_atraso": 80, "faixa": (-5.0, 10.0)},
}

log = logging.getLogger("validacao")


class ErroValidacao(Exception):
    """Dados brutos reprovados na validação."""


def validar_dataframe(nome: str, df: pd.DataFrame, hoje: date | None = None) -> list[str]:
    """Devolve a lista de problemas encontrados (vazia = série OK)."""
    hoje = hoje or date.today()
    regra = REGRAS[nome]
    problemas: list[str] = []

    colunas = {"data", "valor", "serie"}
    if not colunas.issubset(df.columns):
        return [f"{nome}: colunas esperadas {sorted(colunas)}, encontradas {list(df.columns)}"]

    if len(df) < regra["min_linhas"]:
        problemas.append(f"{nome}: apenas {len(df)} linhas (mínimo {regra['min_linhas']})")

    if df["data"].isna().any():
        problemas.append(f"{nome}: há datas nulas")
    if df["data"].duplicated().any():
        problemas.append(f"{nome}: há datas duplicadas")

    validos = df["valor"].dropna()
    if validos.empty:
        problemas.append(f"{nome}: nenhum valor numérico")
    else:
        minimo, maximo = regra["faixa"]
        fora = validos[(validos < minimo) | (validos > maximo)]
        if not fora.empty:
            problemas.append(
                f"{nome}: {len(fora)} valores fora da faixa [{minimo}, {maximo}] "
                f"(ex.: {fora.iloc[0]})"
            )

    if df["data"].notna().any():
        ultimo = pd.to_datetime(df["data"]).max().date()
        atraso = (hoje - ultimo).days
        if atraso > regra["max_atraso"]:
            problemas.append(
                f"{nome}: último dado em {ultimo} ({atraso} dias; tolerância {regra['max_atraso']})"
            )

    return problemas


def validar_diretorio(diretorio: Path = RAW_DIR, hoje: date | None = None) -> None:
    """Valida todos os CSVs. Levanta ErroValidacao se houver qualquer problema."""
    problemas: list[str] = []
    for nome in REGRAS:
        caminho = diretorio / f"{nome}.csv"
        if not caminho.exists():
            problemas.append(f"{nome}: arquivo {caminho} não encontrado")
            continue
        df = pd.read_csv(caminho, parse_dates=["data"])
        problemas.extend(validar_dataframe(nome, df, hoje))

    if problemas:
        raise ErroValidacao("Validação dos dados brutos falhou:\n  - " + "\n  - ".join(problemas))
    log.info("Validação dos dados brutos: OK (%d séries).", len(REGRAS))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        validar_diretorio()
    except ErroValidacao as erro:
        log.error("%s", erro)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
