output "id" {
  description = "Foundry AI Services resource ID."
  value       = azapi_resource.foundry.id
}

output "name" {
  description = "Foundry AI Services resource name."
  value       = azapi_resource.foundry.name
}

output "endpoint" {
  description = "Foundry AI Services endpoint (Content Understanding base URL)."
  value       = azapi_resource.foundry.output.properties.endpoint
}

output "principal_id" {
  description = "System-assigned managed identity principal ID."
  value       = azapi_resource.foundry.output.identity.principalId
}

output "account_capability_host_id" {
  description = "Account-level capability host resource ID."
  value       = azapi_resource.account_capability_host.id
}

# Model deployment names — wired into the auto-written .env.
output "gpt52_deployment_name" {
  description = "Deployment name for gpt-5.2."
  value       = azurerm_cognitive_deployment.gpt52.name
}

output "gpt41_deployment_name" {
  description = "Deployment name for gpt-4.1."
  value       = azurerm_cognitive_deployment.gpt41.name
}

output "gpt41_mini_deployment_name" {
  description = "Deployment name for gpt-4.1-mini."
  value       = azurerm_cognitive_deployment.gpt41_mini.name
}

output "embedding_deployment_name" {
  description = "Deployment name for text-embedding-3-large."
  value       = azurerm_cognitive_deployment.embedding.name
}
