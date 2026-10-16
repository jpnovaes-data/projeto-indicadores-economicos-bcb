# Segurança

## Como os segredos são tratados

- Credenciais do banco e da API do Neon **nunca** ficam no repositório. Em produção elas vivem em GitHub Secrets (`DATABASE_URL`, `DBT_HOST`, `DBT_USER`, `DBT_PASSWORD`, `DBT_DBNAME`). Localmente, em `.env` e `~/.dbt/profiles.yml`, ambos fora do Git.
- O `terraform.tfstate` contém a senha do banco em texto puro e está no `.gitignore`.
- O dashboard publicado no GitHub Pages lê apenas um JSON estático e não tem conexão com o banco.
- O workflow do dashboard usa permissões mínimas, e o CI do Terraform roda sem nenhum secret.

## Se um segredo vazar

1. Troque a senha do role no Neon (Console, Roles, Reset password) e atualize os secrets do GitHub e o `.env` local.
2. Se foi a API key, revogue-a em Account Settings, API Keys, e gere outra.
3. Remover o arquivo do último commit não basta, porque o histórico do Git guarda o valor. Considere o segredo comprometido e rotacione.

## Reportar uma vulnerabilidade

Use a aba **Security** do repositório e a opção de relato privado de vulnerabilidade. Evite abrir issues públicas com detalhes de uma falha.
