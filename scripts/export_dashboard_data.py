"""
Exporta a tabela marts.fato_indicadores_economicos para docs/data.json.

Esse JSON e consumido pela pagina estatica docs/index.html (GitHub Pages).
Roda no GitHub Actions logo depois do dbt, entao o dashboard se atualiza
sozinho a cada execucao do pipeline.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

SAIDA = Path(__file__).parent.parent / "docs" / "data.json"


def main():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL nao encontrada.")

    engine = create_engine(url)
    df = pd.read_sql(
        "select * from marts.fato_indicadores_economicos order by mes", engine
    )

    df["mes"] = pd.to_datetime(df["mes"]).dt.strftime("%Y-%m")

    # O acumulado de 12 meses so e valido quando ha 12 meses de IPCA na janela
    meses_ipca = df["ipca_variacao_mensal"].notna().cumsum()
    df.loc[meses_ipca < 12, "ipca_acumulado_12m"] = None

    df = df.round(4)

    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        "rows": json.loads(df.to_json(orient="records")),
    }

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Exportados {len(df)} meses para {SAIDA}")


if __name__ == "__main__":
    main()
