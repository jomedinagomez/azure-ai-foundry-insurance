output "id" {
  description = "Foundry project resource ID."
  value       = azapi_resource.project.id
}

output "name" {
  description = "Foundry project name."
  value       = azapi_resource.project.name
}

output "principal_id" {
  description = "Foundry project system-assigned managed identity principal ID."
  value       = azapi_resource.project.output.identity.principalId
}
