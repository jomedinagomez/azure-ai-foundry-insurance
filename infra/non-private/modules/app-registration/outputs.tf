output "client_id" {
  description = "Application (client) ID."
  value       = azuread_application.this.client_id
}

output "object_id" {
  description = "Service principal object ID (use for RBAC assignments)."
  value       = azuread_service_principal.this.object_id
  depends_on  = [time_sleep.wait_sp]
}

output "client_secret" {
  description = "Client secret value."
  value       = azuread_application_password.this.value
  sensitive   = true
}

output "tenant_id" {
  description = "Tenant ID of the SP."
  value       = azuread_service_principal.this.application_tenant_id
}
