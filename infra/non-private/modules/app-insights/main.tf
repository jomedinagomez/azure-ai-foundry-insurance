resource "azurerm_log_analytics_workspace" "law" {
  name                = var.law_name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = var.tags
}

resource "azurerm_application_insights" "appinsights" {
  name                = var.appinsights_name
  resource_group_name = var.resource_group_name
  location            = var.location
  workspace_id        = azurerm_log_analytics_workspace.law.id
  application_type    = "web"

  tags = var.tags
}

# Diagnostic settings — Log Analytics Workspace.
resource "azurerm_monitor_diagnostic_setting" "law" {
  name                       = "diag-${var.law_name}"
  target_resource_id         = azurerm_log_analytics_workspace.law.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id

  enabled_log { category = "Audit" }
  enabled_log { category = "SummaryLogs" }

  enabled_metric { category = "AllMetrics" }
}

# Diagnostic settings — Application Insights.
resource "azurerm_monitor_diagnostic_setting" "appinsights" {
  name                       = "diag-${var.appinsights_name}"
  target_resource_id         = azurerm_application_insights.appinsights.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id

  enabled_log { category = "AppAvailabilityResults" }
  enabled_log { category = "AppBrowserTimings" }
  enabled_log { category = "AppEvents" }
  enabled_log { category = "AppMetrics" }
  enabled_log { category = "AppDependencies" }
  enabled_log { category = "AppExceptions" }
  enabled_log { category = "AppPageViews" }
  enabled_log { category = "AppPerformanceCounters" }
  enabled_log { category = "AppRequests" }
  enabled_log { category = "AppSystemEvents" }
  enabled_log { category = "AppTraces" }

  enabled_metric { category = "AllMetrics" }
}
