import math
import sys

import pandas as pd
import pytest

import gerar_profile_dbt as gp
import load_to_neon as ld


def test_parse_url_com_caracteres_especiais_na_senha():
    cfg = gp.parse_url(
        "postgresql://ana:p%40ss%2Fw0rd@ep-x.sa-east-1.aws.neon.tech/neondb?sslmode=require"
    )
    assert cfg["user"] == "ana" and cfg["password"] == "p@ss/w0rd"
    assert cfg["host"] == "ep-x.sa-east-1.aws.neon.tech" and cfg["dbname"] == "neondb"
    assert cfg["sslmode"] == "require" and cfg["port"] == 5432


def test_parse_url_respeita_sslmode_e_porta():
    cfg = gp.parse_url("postgresql://u:s@localhost:6543/db?sslmode=disable")
    assert cfg["sslmode"] == "disable" and cfg["port"] == 6543


@pytest.mark.parametrize("url", ["mysql://u:s@h/db", "not-a-url", "postgresql:///db"])
def test_parse_url_invalida(url):
    with pytest.raises(ValueError):
        gp.parse_url(url)


def test_profile_prod_apenas():
    p = gp.montar_profile("postgresql://u:s@h/db")["dbt_economia"]
    assert p["target"] == "prod" and list(p["outputs"]) == ["prod"]


def test_profile_com_dev_usa_dev_como_padrao_local():
    p = gp.montar_profile("postgresql://u:s@h/db", "postgresql://u:s@h/dev")["dbt_economia"]
    assert p["target"] == "dev" and set(p["outputs"]) == {"dev", "prod"}


def test_profile_target_dev_sem_url_dev_falha():
    with pytest.raises(ValueError):
        gp.montar_profile("postgresql://u:s@h/db", target="dev")

@pytest.mark.skipif(sys.platform == "win32", reason="Windows não aplica permissões POSIX (chmod)")


def test_profile_gerado_com_permissao_restrita(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:s@h/db")
    monkeypatch.delenv("DATABASE_URL_DEV", raising=False)
    destino = tmp_path / "p" / "profiles.yml"
    assert gp.main(["--destino", str(destino), "--target", "prod"]) == 0
    assert oct(destino.stat().st_mode)[-3:] == "600"


def test_nome_de_tabela_desconhecido_e_rejeitado():
    with pytest.raises(ValueError):
        ld._checar_nome("ipca; DROP TABLE raw.ipca")


def test_registros_converte_nan_em_none():
    df = pd.DataFrame(
        {
            "data": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "valor": [1.5, math.nan],
            "serie": ["x", "x"],
        }
    )
    regs = ld._registros(df)
    assert regs[0]["valor"] == 1.5 and regs[1]["valor"] is None
    assert regs[0]["data"].year == 2026


def test_carga_com_csv_ausente_levanta_erro(tmp_path):
    with pytest.raises(FileNotFoundError):
        ld.carregar_serie(engine=None, nome="ipca", diretorio=tmp_path)
