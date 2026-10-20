# Checklist após aplicar a atualização

Itens que **não dá para fazer pelo código** (dependem de acesso ao Neon, ao GitHub ou a decisões suas). Em ordem.

## 1. Segurança (primeiro)
- [ ] Se o `.env` enviado no zip tinha a `DATABASE_URL` real, **redefina a senha da role no Neon** e atualize o secret `DATABASE_URL` e o `.env`. (A varredura do histórico do Git não achou segredos; o risco é só o arquivo ter sido empacotado.)
- [ ] Ao compartilhar o projeto, gere o zip sem `.env`, `.terraform/`, `dbt_economia/target/` e `logs/` (`git archive HEAD -o projeto.zip`).

## 2. Aplicar a atualização
- [ ] Crie uma branch (`git switch -c chore/lapidacao`), copie os arquivos do zip por cima do projeto (ou aplique `lapidacao.patch` com `git apply`) e abra um **pull request**.
- [ ] Rode localmente: `pip install -r requirements-dev.txt`, `make lint`, `make test`.
- [ ] Confirme que o CI **Python CI** ficou verde no PR.

## 3. Primeira execução em produção
- [ ] Rode o **pipeline diário manualmente** (Actions, *Run workflow*) e confira cada etapa.
- [ ] A primeira carga **migra as tabelas `raw` sozinha** (adiciona `ingerido_em` e a chave única em `data`). Se falhar por datas duplicadas, o erro aponta a tabela; hoje não deveria haver duplicatas, pois o teste `unique` do dbt já passava.
- [ ] Abra o dashboard e confira: IPCA 12 meses (agora composto, vai diferir levemente do antigo), Meta Selic e o aviso de desatualização (não deve aparecer).
- [ ] Depois de um run verde, **remova os secrets `DBT_HOST`, `DBT_USER`, `DBT_PASSWORD` e `DBT_DBNAME`**.
- [ ] Opcional: cadastre `ALERT_WEBHOOK_URL` (Slack) para alerta além da issue.

## 4. Dependabot
- [ ] **PRs de Python** (dbt-core, pandas, psycopg2-binary, python-dotenv, requests): já estão contemplados em `requirements.txt` (versões iguais ou mais novas, testadas juntas). Feche-os.
- [ ] **PRs de actions** (checkout, setup-python, deploy-pages, upload-pages-artifact, setup-terraform): são saltos de *major*. As actions foram fixadas por SHA nas versões em uso hoje. Revise um por vez, rodando o pipeline manualmente após cada merge. `deploy-pages` e `upload-pages-artifact` costumam precisar subir juntas.

## 5. Configurações do GitHub
- [ ] Siga a seção "Configurações recomendadas no GitHub" do `SECURITY.md` (proteção da `main` exigindo o check `lint e testes`, secret scanning, push protection, aprovação para forks).

## 6. Opcionais, mas recomendados
- [ ] `pre-commit install` em cada clone.
- [ ] Criar uma **branch de dev no Neon** e definir `DATABASE_URL_DEV` no `.env`.
- [ ] Tirar um novo print do dashboard e substituir `docs/dashboard.png`.
- [ ] Terraform: considerar apertar a restrição `version = "~> 0.6"` do provider para a versão do `.terraform.lock.hcl`. Não alterei a infraestrutura, porque não há como validar com o seu state aqui.
