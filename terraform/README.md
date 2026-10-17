# Runbook de infraestrutura (Terraform)

O Terraform gerencia **apenas o projeto Neon** (PostgreSQL). Ingestão, dbt e dashboard são responsabilidade de outras partes do projeto. O pipeline diário **não executa `terraform apply`**: mudanças de infraestrutura são planejadas, revisadas e aplicadas manualmente.

## Pré-requisitos

- Terraform 1.15 ou superior
- Acesso ao workspace `projeto-economia` no HCP Terraform (a organização está no bloco `cloud` do `provider.tf`)
- API key do Neon

## State remoto

- O state fica no HCP Terraform, no workspace `projeto-economia`, com **Execution Mode: Local**. Os comandos rodam no seu terminal ou no runner do GitHub Actions, e o HCP só guarda o state.
- O state pode conter a senha do banco. Restrinja o acesso ao workspace e aos tokens.
- Antes de qualquer recuperação, consulte o state no HCP. Não migre nem recrie o state sem necessidade.

## Autenticação

HCP Terraform, no terminal local:

```powershell
terraform login
```

API do Neon, definida só na sessão. O texto entre aspas do `Read-Host` é apenas o rótulo do prompt: a chave é digitada ou colada depois, e não aparece na tela.

```powershell
$secureKey = Read-Host "Cole a NEON_API_KEY" -AsSecureString
$env:NEON_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
Remove-Variable secureKey
$env:NEON_API_KEY.Length      # confira o tamanho, nunca imprima a chave
```

Ao terminar:

```powershell
Remove-Item Env:NEON_API_KEY -ErrorAction SilentlyContinue
```

Nunca coloque a chave em arquivos `.tf`, `.tfvars`, commits ou logs. No GitHub Actions, as credenciais vêm dos secrets `TF_API_TOKEN` e `NEON_API_KEY_CI`.

## Fluxo normal de mudança

A partir de `terraform/`:

```powershell
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -out=tfplan
```

Leia o plano inteiro. Procure por `-/+` (substituição) e `-` (destruição), e por mudanças em região, versão do PostgreSQL ou configuração do projeto. Se o plano destruir ou substituir `neon_project.projeto_economia`, **pare e investigue a causa**.

Quando o plano estiver como esperado:

```powershell
terraform apply tfplan
terraform plan
```

O segundo `plan` deve retornar `No changes`. Apague o `tfplan` depois do uso e nunca o versione.

## Proteção contra destruição

O recurso tem `lifecycle { prevent_destroy = true }`, que faz o Terraform recusar qualquer plano que o destrua.

### Destruir de propósito

Só faça isso se realmente precisar encerrar o projeto.

1. Confirme que não há dados a preservar e faça backup do que for necessário.
2. Remova o bloco `lifecycle` em um commit separado e rode `terraform plan`.
3. Revise o plano e só então rode `terraform destroy`.
4. Se o projeto continuar existindo, restaure o bloco `lifecycle`.

Não remova a proteção apenas para fazer um plano passar.

## Importar um projeto existente

Só é necessário quando o recurso existe no Neon mas não está no state.

```powershell
terraform init
terraform state list       # se o recurso já aparecer, NÃO importe de novo
terraform import neon_project.projeto_economia ID_DO_PROJETO
terraform plan
```

O ID está em Settings, General, no console do Neon. Ajuste o `main.tf` até o plano retornar `No changes`. Nunca crie outro projeto para resolver um problema de state.

## Workflows de Terraform

- **Terraform CI:** `fmt -check`, `init -backend=false` e `validate`. Não usa credenciais.
- **Terraform Plan:** inicializa com o state remoto e gera um plano somente leitura, com `TF_API_TOKEN` e `NEON_API_KEY_CI`. Nunca aplica mudanças.

## Recuperação

**State ausente ou inconsistente:** interrompa qualquer `apply`, confirme a organização e o workspace no `provider.tf`, verifique a autenticação, consulte o state e o histórico no HCP e confirme que o projeto ainda existe no Neon. O banco pode continuar existindo mesmo quando o state não está acessível.

**Senha do banco alterada:** atualize `DATABASE_URL`, `DBT_*`, o `.env` e o `~/.dbt/profiles.yml` e rode o pipeline para confirmar o acesso.

**API key do Neon ou token do HCP expostos:** revogue, gere novos e atualize `NEON_API_KEY_CI` ou `TF_API_TOKEN`. Atualizar o secret não invalida o valor antigo, a revogação é obrigatória. Rode o workflow de plano para confirmar.

## Checklist antes de concluir uma mudança

- Formatação e `validate` passaram.
- O plano foi lido por inteiro, sem destruições ou substituições inesperadas.
- Os checks do GitHub Actions passaram.
- O plano final retornou `No changes`.
- Nenhuma credencial, state ou arquivo de plano foi versionado.
