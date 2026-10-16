terraform {
  required_providers {
    neon = {
      source  = "kislerdm/neon"
      version = "~> 0.6"
    }
  }
}

# A api_key nao fica hardcoded aqui.
# O provider le automaticamente da variavel de ambiente NEON_API_KEY.
provider "neon" {}
