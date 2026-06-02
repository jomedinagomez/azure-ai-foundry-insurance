output "law_id" {
  description = "Log Analytics Workspace resource ID."
  value       = azurerm_log_analytics_workspace.law.id
}

output "law_workspace_id" {
  description = "Log Analytics Workspace ID (GUID)."
  value       = azurerm_log_analytics_workspace.law.workspace_id
}

output "appinsights_id" {
  description = "Application Insights resource ID."
  value       = azurerm_application_insights.appinsights.id
}

output "appinsights_connection_string" {
  description = "Application Insights connection string."
  value       = azurerm_application_insights.appinsights.connection_string
  sensitive   = true
}

output "appinsights_instrumentation_key" {
  description = "Application Insights instrumentation key."
  value       = azurerm_application_insights.appinsights.instrumentation_key
  sensitive   = true
}
