"""
Exporta marts.fato_indicadores_economicos para docs/data.json.

Esse JSON é consumido pela página estática docs/index.html (GitHub Pages) e é
regenerado a cada execução do pipeline. Além das linhas mensais, o arquivo
inclui metadados com a data do último dado de cada série, usados pelo
dashboard para avisar quando os dados estiverem desatualizados.

O acumulado de 12 meses do IPCA vem pronto do dbt (composto, nulo até haver
12 meses consecutivos): nenhuma regra de negócio é aplicada aqui.
"""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

SAIDA = Path(__file__).parent.parent / "docs" / "data.json"

ULTIMA_DATA = {
    "dolar": "staging.stg_cambio_dolar",
    "selic": "staging.stg_selic",
    "ipca": "staging.stg_ipca",
    "igpm": "staging.stg_igpm",
}

COLUNAS = [
    "mes",
    "dolar_medio_mes",
    "dolar_minimo_mes",
    "dolar_maximo_mes",
    "meta_selic_media_mes",
    "ipca_variacao_mensal",
    "ipca_acumulado_12m",
    "igpm_variacao_mensal",
]


def montar_payload(df: pd.DataFrame, ultimas_datas: dict[str, str], agora: datetime) -> dict:
    """Monta o JSON do dashboard (função pura, testável sem banco)."""
    faltando = [c for c in COLUNAS if c not in df.columns]
    if faltando:
        raise RuntimeError(f"Colunas ausentes no mart: {faltando}")
    if df.empty:
        raise RuntimeError("O mart está vazio; abortando para não publicar um dashboard em branco.")

    df = df[COLUNAS].copy()
    df["mes"] = pd.to_datetime(df["mes"]).dt.strftime("%Y-%m")
    df = df.round(4)

    return {
        "schema_version": 2,
        "updated_at": agora.strftime("%d/%m/%Y %H:%M UTC"),
        "updated_at_iso": agora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dados_ate": ultimas_datas,
        "rows": json.loads(df.to_json(orient="records")),
    }


def main() -> int:
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não encontrada.")

    engine = create_engine(url)
    with engine.connect() as conn:
        df = pd.read_sql(text("select * from marts.fato_indicadores_economicos order by mes"), conn)
        ultimas = {
            serie: conn.execute(text(f"select max(data)::date from {tabela}"))
            .scalar_one()
            .isoformat()
            for serie, tabela in ULTIMA_DATA.items()
        }

    payload = montar_payload(df, ultimas, datetime.now(UTC))

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    temporario = SAIDA.with_suffix(".json.tmp")  # escrita atômica: nunca deixa JSON pela metade
    temporario.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporario.replace(SAIDA)
    print(f"Exportados {len(payload['rows'])} meses para {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
