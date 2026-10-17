# Segurança

## Como os segredos são tratados

- Credenciais, tokens e chaves de API nunca são versionados.
- O pipeline de dados usa GitHub Secrets: `DATABASE_URL`, `DBT_HOST`, `DBT_USER`, `DBT_PASSWORD` e `DBT_DBNAME`.
- A automação de infraestrutura usa `TF_API_TOKEN` (HCP Terraform) e `NEON_API_KEY_CI` (API do Neon, no plano).
- Localmente, as credenciais ficam em `.env` e `~/.dbt/profiles.yml`, fora do Git.
- O state do Terraform fica no HCP Terraform e pode conter informações sensíveis, então o acesso ao workspace deve ser restrito.
- O dashboard publicado lê apenas um JSON estático. O navegador não recebe credenciais nem se conecta ao banco.
- O workflow `Terraform CI` roda sem credenciais. O `Terraform Plan` usa os secrets acima e nunca aplica mudanças.

## Se um segredo vazar

Considere o valor comprometido, mesmo que o arquivo seja removido depois, porque o histórico do Git o preserva. Atualizar um secret no GitHub não invalida o valor antigo: é preciso revogar ou rotacionar.

1. **Senha do banco:** redefina a senha da role no Neon e atualize os secrets do GitHub, o `.env` e o `~/.dbt/profiles.yml`.
2. **API key do Neon:** revogue a chave, gere outra e atualize `NEON_API_KEY_CI` e os ambientes locais.
3. **Token do HCP Terraform:** revogue o token, gere outro e atualize `TF_API_TOKEN`.

Depois da rotação, rode os workflows pertinentes para confirmar que as novas credenciais funcionam.

## State do Terraform

- Não versione `terraform.tfstate`, backups de state nem arquivos de plano.
- Não compartilhe state por chat, e-mail ou serviços sem proteção.
- Antes de qualquer importação ou recuperação, consulte o state existente no HCP Terraform para evitar duplicação de recursos.

## Reportar uma vulnerabilidade

Use o relato privado de vulnerabilidades na aba **Security** do repositório. Evite publicar detalhes ou credenciais em issues públicas.
