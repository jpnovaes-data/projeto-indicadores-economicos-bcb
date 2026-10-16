resource "neon_project" "projeto_economia" {
  name       = "projeto-economia"
  region_id  = "aws-sa-east-1" # Sao Paulo - regiao real do projeto ja criado
  pg_version = 17

  history_retention_seconds = 21600 # limite do plano free do Neon (6h)

  branch {
    name = "production"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# O Neon cria automaticamente um endpoint e um role default
# junto com o projeto. Vamos apenas ler essas informacoes de saida abaixo.