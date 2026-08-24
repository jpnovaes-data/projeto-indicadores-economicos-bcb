"""
Carrega os CSVs gerados por ingest_bcb.py no banco Postgres (Neon).

Cria o schema "raw" e uma tabela por serie economica, sobrescrevendo
os dados a cada execucao (estrategia simples: full refresh).

Requer um arquivo .env na raiz do projeto com:
    DATABASE_URL=postgresql://usuario:senha@host/db?sslmode=require
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

SERIES = ["cambio_dolar", "ipca", "selic", "igpm"]


def conectar():
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL nao encontrada. Copie .env.example para .env "
            "e preencha com a connection string do Neon."
        )

    engine = create_engine(database_url)
    return engine


def criar_schema(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
    print("Schema 'raw' verificado/criado.")


def carregar_serie(engine, nome: str):
    caminho_csv = RAW_DIR / f"{nome}.csv"

    if not caminho_csv.exists():
        print(f"  AVISO: {caminho_csv} nao encontrado, pulando '{nome}'.")
        return

    df = pd.read_csv(caminho_csv, parse_dates=["data"])

    with engine.begin() as conn:
        existe = conn.execute(text(
            "SELECT to_regclass(:tabela)"
        ), {"tabela": f"raw.{nome}"}).scalar()

        if existe:
            # TRUNCATE em vez de DROP: mantem a tabela intacta, entao views
            # do dbt (staging.*) que dependem dela nao quebram.
            conn.execute(text(f"TRUNCATE TABLE raw.{nome}"))

    df.to_sql(
        name=nome,
        con=engine,
        schema="raw",
        if_exists="append",  # a tabela ja foi limpa (ou sera criada agora)
        index=False,
    )

    print(f"  -> '{nome}': {len(df)} registros carregados em raw.{nome}")


def main():
    print("Conectando ao Neon...")
    engine = conectar()

    criar_schema(engine)

    print("\nCarregando series:")
    for nome in SERIES:
        carregar_serie(engine, nome)

    print("\nCarga concluida.")


if __name__ == "__main__":
    main()
