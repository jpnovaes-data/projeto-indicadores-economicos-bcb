
terraform {
  required_version = ">= 1.15.8, < 2.0.0"

  required_providers {
    neon = {
      source  = "kislerdm/neon"
      version = "~> 0.6"
    }
  }

  cloud {
    organization = "projeto-economia"

    workspaces {
      name = "projeto-economia"
    }
  }
}

# A API key não fica hardcoded aqui.
# O provider lê a variável de ambiente NEON_API_KEY.
provider "neon" {}