# Runbook de infraestrutura (Terraform)

O Terraform gerencia **apenas o projeto Neon** (Postgres). Ingestão, dbt e dashboard são responsabilidade de outras partes do pipeline. O pipeline diário **não executa Terraform**: mudanças de infraestrutura são aplicadas manualmente, depois de revisar o `plan`.

## Pré-requisitos

- Terraform 1.15 ou superior
- API key do Neon (Account Settings, API Keys), exportada só na sessão do terminal:

```powershell
$env:NEON_API_KEY = "sua_api_key"
```

Nunca coloque a key em arquivos `.tf`, `.tfvars` ou no histórico do terminal compartilhado.

## Fluxo normal de mudança

```powershell
cd terraform
terraform fmt
terraform validate
terraform plan -out=tfplan
```

Leia o plano antes de aplicar. Procure por `-/+` (destruir e recriar) e `-` (destruir). Se aparecer qualquer um deles em `neon_project`, **pare e investigue**. Quando o plano estiver como esperado:

```powershell
terraform apply tfplan
```

O `-out` garante que será aplicado exatamente o plano que você revisou.

## Proteção contra destruição acidental

O recurso `neon_project` tem `lifecycle { prevent_destroy = true }`. Qualquer plano que destrua ou substitua o banco falha com erro. Para destruir de propósito, remova essas linhas, rode o `plan`, confira e só então aplique.

## Importar um projeto que já existe

O ID do projeto aparece em Settings, General, no console do Neon.

```powershell
terraform init
terraform import neon_project.projeto_economia ID_DO_PROJETO
terraform plan
```

Ajuste o `main.tf` até o plano retornar `No changes`. Só então aplique qualquer outra mudança.

## State: o ponto mais sensível

O arquivo `terraform.tfstate` guarda a **senha do banco em texto puro**. Regras:

- Nunca commitar (já está no `.gitignore`).
- Não compartilhar por chat, e-mail ou nuvem sem criptografia.
- Fazer backup somente em local privado.

### Migrar o state para um backend remoto

Um state só no seu computador se perde junto com o disco. Uma opção é o HCP Terraform (confira os limites do plano gratuito antes de escolher):

1. Crie uma organização e um workspace chamado `projeto-economia` no HCP Terraform, com **Execution Mode: Local**. Assim o `plan` continua usando a `NEON_API_KEY` do seu terminal.
2. Rode `terraform login`.
3. Adicione ao bloco `terraform` do `provider.tf`:

```hcl
cloud {
  organization = "SUA_ORGANIZACAO"
  workspaces {
    name = "projeto-economia"
  }
}
```

4. Rode `terraform init -migrate-state` e confirme.
5. Rode `terraform plan` (deve dar `No changes`) e só então apague os `terraform.tfstate*` locais.

## Recuperação

- **Perdeu o state:** o banco continua existindo no Neon. Rode `terraform init` e o `terraform import` acima.
- **Senha do banco trocada:** atualize `.env`, `~/.dbt/profiles.yml` e os GitHub Secrets. O Terraform lê a senha atual do Neon no próximo `plan`.

## Verificação automática

O workflow `Terraform CI` roda `fmt -check`, `init -backend=false` e `validate` a cada mudança em `terraform/`. Ele não usa credenciais e não consulta o banco.
