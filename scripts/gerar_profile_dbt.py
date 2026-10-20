"""
Gera o profiles.yml do dbt a partir das variáveis de ambiente, sem copiar
senha à mão e sem precisar de 5 secrets separados.

    DATABASE_URL       -> target "prod" (obrigatória)
    DATABASE_URL_DEV   -> target "dev"  (opcional; ex.: branch de dev do Neon)

Uso (local ou CI):
    python scripts/gerar_profile_dbt.py                # escreve ~/.dbt/profiles.yml
    python scripts/gerar_profile_dbt.py --target prod  # força o target padrão

Nada sensível é impresso. O arquivo é criado com permissão 0600.
"""

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import yaml
from dotenv import load_dotenv


def parse_url(url: str) -> dict:
    """Converte uma connection string PostgreSQL em campos do profile dbt."""
    partes = urlparse(url)
    if partes.scheme not in ("postgres", "postgresql") or not partes.hostname:
        raise ValueError("URL inválida: esperado postgresql://usuario:senha@host/db")
    sslmode = parse_qs(partes.query).get("sslmode", ["require"])[0]
    return {
        "type": "postgres",
        "host": partes.hostname,
        "user": unquote(partes.username or ""),
        "password": unquote(partes.password or ""),
        "port": partes.port or 5432,
        "dbname": partes.path.lstrip("/") or "postgres",
        "schema": "raw",
        "sslmode": sslmode,
        "threads": 4,
    }


def montar_profile(url_prod: str, url_dev: str | None = None, target: str | None = None) -> dict:
    saidas = {"prod": parse_url(url_prod)}
    if url_dev:
        saidas["dev"] = parse_url(url_dev)
    padrao = target or ("dev" if "dev" in saidas else "prod")
    if padrao not in saidas:
        raise ValueError(f"target '{padrao}' indisponível; defina DATABASE_URL_DEV para usar 'dev'")
    return {"dbt_economia": {"target": padrao, "outputs": saidas}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera ~/.dbt/profiles.yml a partir de DATABASE_URL"
    )
    parser.add_argument("--target", choices=["dev", "prod"], help="target padrão do profile")
    parser.add_argument("--destino", type=Path, default=Path.home() / ".dbt" / "profiles.yml")
    args = parser.parse_args(argv)

    load_dotenv()
    url_prod = os.getenv("DATABASE_URL")
    if not url_prod:
        print("DATABASE_URL não definida.", file=sys.stderr)
        return 1

    try:
        profile = montar_profile(url_prod, os.getenv("DATABASE_URL_DEV"), args.target)
    except ValueError as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1

    args.destino.parent.mkdir(parents=True, exist_ok=True)
    args.destino.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    args.destino.chmod(0o600)
    alvos = ", ".join(profile["dbt_economia"]["outputs"])
    padrao = profile["dbt_economia"]["target"]
    print(f"Profile gerado em {args.destino} (targets: {alvos}; padrão: {padrao})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
