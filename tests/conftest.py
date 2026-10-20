"""Fixtures compartilhadas. Os testes de integração só rodam com TEST_DATABASE_URL."""

import os
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

RAIZ = Path(__file__).parent.parent
PROJETO_DBT = RAIZ / "dbt_economia"


# ---------------------------------------------------------------- dados sintéticos
def serie_diaria(nome: str, base: float, dias: int = 700) -> pd.DataFrame:
    """Série diária terminando ontem, com pequena oscilação determinística."""
    fim = pd.Timestamp(date.today() - timedelta(days=1))
    datas = pd.date_range(end=fim, periods=dias, freq="D")
    valores = [round(base + 0.3 * ((i % 20) - 10) / 10, 4) for i in range(dias)]
    return pd.DataFrame({"data": datas, "valor": valores, "serie": nome})


def serie_mensal(nome: str, base: float, meses: int = 30) -> pd.DataFrame:
    """Série mensal (dia 1) terminando no mês passado."""
    ultimo = pd.Timestamp(date.today()).replace(day=1) - pd.DateOffset(months=1)
    datas = pd.date_range(end=ultimo, periods=meses, freq="MS")
    valores = [round(base + 0.05 * ((i % 7) - 3), 2) for i in range(meses)]
    return pd.DataFrame({"data": datas, "valor": valores, "serie": nome})


def series_sinteticas() -> dict[str, pd.DataFrame]:
    return {
        "cambio_dolar": serie_diaria("cambio_dolar", 5.0),
        "selic": serie_diaria("selic", 14.0),
        "ipca": serie_mensal("ipca", 0.4),
        "igpm": serie_mensal("igpm", 0.3),
    }


def escrever_csvs(diretorio: Path, series: dict[str, pd.DataFrame]) -> None:
    diretorio.mkdir(parents=True, exist_ok=True)
    for nome, df in series.items():
        df.to_csv(diretorio / f"{nome}.csv", index=False)


@pytest.fixture
def series():
    return series_sinteticas()


# ------------------------------------------------------------------ banco de teste
@pytest.fixture(scope="session")
def url_teste() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL não definida (testes de integração desativados)")
    nome_banco = make_url(url).database or ""
    if "test" not in nome_banco.lower():
        # Proteção: estes testes DROPAM schemas. Nunca rodam em banco que não seja de teste.
        pytest.exit(
            f"Recusado: o banco '{nome_banco}' não parece ser de teste "
            "(o nome precisa conter 'test').",
            returncode=2,
        )
    return url


@pytest.fixture
def engine_teste(url_teste) -> Engine:
    engine = create_engine(url_teste)
    with engine.begin() as conn:
        conn.execute(
            text(
                "DROP SCHEMA IF EXISTS raw CASCADE; DROP SCHEMA IF EXISTS staging CASCADE; "
                "DROP SCHEMA IF EXISTS marts CASCADE; CREATE SCHEMA raw"
            )
        )
    yield engine
    engine.dispose()


# ----------------------------------------------------------------------------- dbt
def executar_dbt(*args: str, url: str, pasta: Path) -> subprocess.CompletedProcess:
    """Roda o dbt com profile temporário apontando para o banco de teste."""
    import yaml

    from gerar_profile_dbt import montar_profile  # scripts/ está no pythonpath

    perfil = pasta / "profiles"
    perfil.mkdir(exist_ok=True)
    (perfil / "profiles.yml").write_text(
        yaml.safe_dump(montar_profile(url, target="prod")), encoding="utf-8"
    )
    exe = shutil.which("dbt") or str(Path(sys.executable).parent / "dbt")
    ambiente = {
        **os.environ,
        "DBT_TARGET_PATH": str(pasta / "target"),
        "DBT_LOG_PATH": str(pasta / "logs"),
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "False",
    }
    return subprocess.run(
        [exe, *args, "--project-dir", str(PROJETO_DBT), "--profiles-dir", str(perfil)],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=300,
    )
