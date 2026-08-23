output "connection_uri" {
  description = "Connection string do banco, gerada pelo Neon."
  value       = neon_project.projeto_economia.connection_uri
  sensitive   = true
}

output "project_id" {
  description = "ID do projeto no Neon (util para referencia futura)."
  value       = neon_project.projeto_economia.id
}
