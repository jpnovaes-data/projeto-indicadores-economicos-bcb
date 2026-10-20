"""
Carrega os CSVs gerados por ingest_bcb.py no PostgreSQL (Neon).

Estratégia: UPSERT idempotente, tudo numa ÚNICA transação por série.
  - nunca esvazia a tabela: se algo falhar, o rollback preserva os dados antigos;
  - rodar duas vezes seguidas não duplica nada (chave única em "data");
  - o histórico que sai da janela da API continua no banco (carga incremental);
  - "ingerido_em" registra quando cada linha foi inserida/atualizada, base do
    teste de frescor no dbt.

Requer a variável DATABASE_URL (arquivo .env local ou secret no GitHub):
    DATABASE_URL=postgresql://usuario:senha@host/db?sslmode=require
"""

import argparse
import logging
import math
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from validacao import ErroValidacao, validar_diretorio

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
SERIES = ["cambio_dolar", "ipca", "selic", "igpm"]

log = logging.getLogger("load_to_neon")


def conectar(url: str | None = None) -> Engine:
    load_dotenv()
    database_url = url or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL não encontrada. Copie .env.example para .env "
            "e preencha com a connection string do Neon."
        )
    return create_engine(database_url, pool_pre_ping=True)


def criar_schema(conn: Connection) -> None:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))


def _checar_nome(nome: str) -> str:
    if nome not in SERIES:  # nome vai direto no SQL: só aceitamos os conhecidos
        raise ValueError(f"Série desconhecida: {nome!r}")
    return nome


def garantir_tabela(conn: Connection, nome: str) -> None:
    """Cria a tabela se não existir e migra tabelas criadas pela versão antiga.

    As tabelas antigas (criadas pelo pandas) não tinham "ingerido_em" nem chave
    única. Os ALTERs abaixo são aditivos e não quebram as views do dbt.
    """
    _checar_nome(nome)
    conn.execute(
        text(f"""
        CREATE TABLE IF NOT EXISTS raw.{nome} (
            data        TIMESTAMP,
            valor       DOUBLE PRECISION,
            serie       TEXT,
            ingerido_em TIMESTAMPTZ DEFAULT now()
        )
    """)
    )
    conn.execute(
        text(
            f"ALTER TABLE raw.{nome} ADD COLUMN IF NOT EXISTS ingerido_em TIMESTAMPTZ DEFAULT now()"
        )
    )
    conn.execute(text(f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{nome}_data ON raw.{nome} (data)"))


def _registros(df: pd.DataFrame) -> list[dict]:
    registros = []
    for linha in df.itertuples(index=False):
        valor = None if linha.valor is None or math.isnan(linha.valor) else float(linha.valor)
        registros.append(
            {
                "data": pd.Timestamp(linha.data).to_pydatetime(),
                "valor": valor,
                "serie": str(linha.serie),
            }
        )
    return registros


def carregar_serie(engine: Engine, nome: str, diretorio: Path = RAW_DIR) -> int:
    """Faz o upsert de uma série. Levanta exceção se o CSV não existir."""
    _checar_nome(nome)
    caminho = diretorio / f"{nome}.csv"
    if not caminho.exists():
        raise FileNotFoundError(f"{caminho} não encontrado (rode a ingestão primeiro)")

    df = pd.read_csv(caminho, parse_dates=["data"])
    registros = _registros(df)

    with engine.begin() as conn:  # uma transação: tudo ou nada
        garantir_tabela(conn, nome)
        conn.execute(
            text(f"""
                INSERT INTO raw.{nome} (data, valor, serie, ingerido_em)
                VALUES (:data, :valor, :serie, now())
                ON CONFLICT (data) DO UPDATE
                   SET valor = EXCLUDED.valor,
                       serie = EXCLUDED.serie,
                       ingerido_em = now()
            """),
            registros,
        )
        total = conn.execute(text(f"SELECT count(*) FROM raw.{nome}")).scalar_one()
        if total < len(df):  # o banco jamais deve ficar com MENOS que o CSV
            raise RuntimeError(f"raw.{nome} ficou com {total} linhas, CSV tem {len(df)}")

    log.info("  -> '%s': %d registros do CSV (tabela agora com %d)", nome, len(df), total)
    return len(df)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument(
        "--pular-validacao",
        action="store_true",
        help="não valida os CSVs antes da carga (uso excepcional)",
    )
    args = parser.parse_args(argv)

    if not args.pular_validacao:
        try:
            validar_diretorio()
        except ErroValidacao as erro:
            log.error("%s\nCarga abortada; o banco não foi alterado.", erro)
            return 1

    log.info("Conectando ao banco...")
    engine = conectar()
    with engine.begin() as conn:
        criar_schema(conn)

    falhas = []
    log.info("Carregando séries:")
    for nome in SERIES:
        try:
            carregar_serie(engine, nome)
        except Exception as erro:  # noqa: BLE001 - registramos e seguimos para o resumo
            log.error("  ERRO em '%s': %s", nome, erro)
            falhas.append(nome)

    if falhas:
        log.error("Carga FALHOU para: %s", ", ".join(falhas))
        return 1
    log.info("Carga concluída.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
