# Segurança

## Como os segredos são tratados

- Credenciais, tokens e chaves de API nunca são versionados.
- O pipeline de dados usa **um único** GitHub Secret de banco: `DATABASE_URL`. O profile do dbt é derivado dele por `scripts/gerar_profile_dbt.py` durante a execução, então os antigos `DBT_HOST`, `DBT_USER`, `DBT_PASSWORD` e `DBT_DBNAME` **não são mais necessários** e podem ser removidos.
- `ALERT_WEBHOOK_URL` é opcional (webhook compatível com Slack para alertas de falha).
- A automação de infraestrutura usa `TF_API_TOKEN` (HCP Terraform) e `NEON_API_KEY_CI` (API do Neon, no plano).
- Localmente, as credenciais ficam em `.env` e `~/.dbt/profiles.yml` (gerado com permissão 0600), fora do Git.
- O state do Terraform fica no HCP Terraform e pode conter informações sensíveis, então o acesso ao workspace deve ser restrito.
- O dashboard publicado lê apenas um JSON estático. O navegador não recebe credenciais nem se conecta ao banco.
- O `Terraform CI` roda sem credenciais. O `Terraform Plan` usa os secrets acima, nunca aplica mudanças e **não roda para PRs do Dependabot nem de forks**.
- **Permissões mínimas por job:** o workflow começa com `contents: read`; `pages: write` e `id-token: write` existem só no job de deploy, e `issues: write` só no job de alerta.
- **Actions fixadas por SHA** de commit (com o número da versão em comentário). O Dependabot atualiza SHA e comentário nos PRs.
- **Barreira local:** o hook `gitleaks` (pre-commit) bloqueia commits com segredos. Ative com `pip install -r requirements-dev.txt && pre-commit install`.
- **Testes de integração** se recusam a rodar contra bancos cujo nome não contenha `test`.

## Configurações recomendadas no GitHub (manuais)

Não vivem no código, então precisam ser conferidas em **Settings** do repositório:

1. **Branches, regra para `main`:** exigir pull request, exigir os checks **`lint e testes`** (workflow Python CI) e **`Terraform Plan`**, e bloquear force push.
   *O `Terraform Plan` roda em todo PR e sempre reporta status (sem mudanças em `terraform/`, termina em segundos), então pode ser obrigatório sem travar PRs. Já o `Terraform CI` tem filtro de pasta e não deve ser marcado como obrigatório: nos PRs que não tocam em `terraform/` ele nunca roda, e o PR ficaria preso em "Expected - Waiting for status to be reported".*
2. **Actions, General:** em *Fork pull request workflows*, exigir aprovação para contribuidores externos; em *Workflow permissions*, deixar **Read repository contents** como padrão.
3. **Secrets:** manter só os necessários (`DATABASE_URL`, `TF_API_TOKEN`, `NEON_API_KEY_CI` e, opcionalmente, `ALERT_WEBHOOK_URL`).
4. **Security, Code security:** ativar *Secret scanning*, *Push protection* e *Dependabot alerts*.
5. **Notifications:** acompanhar o repositório (*Watch*) para receber por e-mail as issues `pipeline-falhou`.

## Agendamento (cron)

O GitHub desativa workflows agendados de repositórios públicos após 60 dias sem atividade no repositório. Se o dashboard exibir o aviso de que o pipeline não atualiza há dias, confira a aba **Actions** e reative o workflow, se preciso.

## Se um segredo vazar

Considere o valor comprometido, mesmo que o arquivo seja removido depois, porque o histórico do Git o preserva. Atualizar um secret no GitHub não invalida o valor antigo: é preciso revogar ou rotacionar.

1. **Senha do banco:** redefina a senha da role no Neon e atualize o secret `DATABASE_URL` e o `.env` (depois rode `python scripts/gerar_profile_dbt.py` para regenerar o profile).
2. **API key do Neon:** revogue a chave, gere outra e atualize `NEON_API_KEY_CI` e os ambientes locais.
3. **Token do HCP Terraform:** revogue o token, gere outro e atualize `TF_API_TOKEN`.
4. **Webhook de alerta:** gere outro no serviço de destino e atualize `ALERT_WEBHOOK_URL`.

Depois da rotação, rode os workflows pertinentes para confirmar que as novas credenciais funcionam.

## State do Terraform

- Não versione `terraform.tfstate`, backups de state nem arquivos de plano.
- Não compartilhe state por chat, e-mail ou serviços sem proteção.
- Antes de qualquer importação ou recuperação, consulte o state existente no HCP Terraform para evitar duplicação de recursos.

## Reportar uma vulnerabilidade

Use o relato privado de vulnerabilidades na aba **Security** do repositório. Evite publicar detalhes ou credenciais em issues públicas.
