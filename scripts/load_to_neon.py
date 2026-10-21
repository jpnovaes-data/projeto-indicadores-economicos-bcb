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
from sqlalchemy import Column, DateTime, Float, MetaData, Table, Text, create_engine, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, Engine

from validacao import ErroValidacao, validar_diretorio

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
SERIES = ["cambio_dolar", "ipca", "selic", "igpm"]

# Linhas por comando INSERT. Cada comando é UMA ida e volta à rede: com o banco longe do
# runner (GitHub nos EUA, Neon em São Paulo), enviar linha a linha leva minutos.
LOTE = 1000

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


def _tabela(nome: str) -> Table:
    """Descrição da tabela raw.<nome> para o SQLAlchemy montar o INSERT em lotes."""
    _checar_nome(nome)
    return Table(
        nome,
        MetaData(),
        Column("data", DateTime),
        Column("valor", Float),
        Column("serie", Text),
        Column("ingerido_em", DateTime(timezone=True)),
        schema="raw",
    )


def _upsert_em_lotes(conn: Connection, nome: str, registros: list[dict]) -> None:
    """INSERT ... ON CONFLICT em comandos de várias linhas (LOTE por comando).

    ~3.500 linhas viram 4 comandos em vez de 3.500. `ingerido_em` usa o DEFAULT now()
    da tabela nos inserts e é atualizado explicitamente nos conflitos.
    """
    tabela = _tabela(nome)
    for i in range(0, len(registros), LOTE):
        comando = pg_insert(tabela).values(registros[i : i + LOTE])
        comando = comando.on_conflict_do_update(
            index_elements=[tabela.c.data],
            set_={
                "valor": comando.excluded.valor,
                "serie": comando.excluded.serie,
                "ingerido_em": func.now(),
            },
        )
        conn.execute(comando)


def carregar_serie(engine: Engine, nome: str, diretorio: Path = RAW_DIR) -> int:
    """Faz o upsert de uma série. Levanta exceção se o CSV não existir."""
    _checar_nome(nome)
    caminho = diretorio / f"{nome}.csv"
    if not caminho.exists():
        raise FileNotFoundError(f"{caminho} não encontrado (rode a ingestão primeiro)")

    df = pd.read_csv(caminho, parse_dates=["data"])
    # Duas linhas com a mesma data no MESMO comando quebrariam o ON CONFLICT; fica a última.
    df = df.drop_duplicates(subset="data", keep="last")
    registros = _registros(df)

    with engine.begin() as conn:  # uma transação: tudo ou nada
        garantir_tabela(conn, nome)
        _upsert_em_lotes(conn, nome, registros)
        total = conn.execute(text(f"SELECT count(*) FROM raw.{nome}")).scalar_one()
        if total < len(registros):  # o banco jamais deve ficar com MENOS que o CSV
            raise RuntimeError(f"raw.{nome} ficou com {total} linhas, CSV tem {len(registros)}")

    log.info("  -> '%s': %d registros do CSV (tabela agora com %d)", nome, len(registros), total)
    return len(registros)


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
