# =============================================================================
# Developer RBAC — roles required by the workshop API + notebooks + UI.
# Authentication uses DefaultAzureCredential / `az login`, so all data-plane
# access is scoped to the signed-in developer's object_id.
# =============================================================================

# Foundry account — Content Understanding data-plane access.
resource "azurerm_role_assignment" "dev_foundry_cognitive_services_user" {
  scope                = var.foundry_resource_id
  role_definition_name = "Cognitive Services User"
  principal_id         = var.developer_object_id
}

# Foundry account — Content Understanding multi-modal analyzer operations
# (deploy/list/analyze for proClaimsV1, proFraudV1, SOV, SEC, etc.). The data
# action Microsoft.CognitiveServices/accounts/MultiModalIntelligence/analyzers:analyze/action
# is not covered by Cognitive Services User.
resource "azurerm_role_assignment" "dev_foundry_cu_contributor" {
  scope                = var.foundry_resource_id
  role_definition_name = "Cognitive Services Content Understanding Contributor"
  principal_id         = var.developer_object_id
}

# Foundry account — Azure OpenAI data-plane access (chat completions, embeddings).
resource "azurerm_role_assignment" "dev_foundry_openai_user" {
  scope                = var.foundry_resource_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = var.developer_object_id
}

# Foundry project — control-plane operations (create analyzers, manage connections).
resource "azurerm_role_assignment" "dev_project_ai_developer" {
  scope                = var.foundry_project_id
  role_definition_name = "Azure AI Developer"
  principal_id         = var.developer_object_id
}

# Application Insights — telemetry read/write for App Insights workbook + logging.
resource "azurerm_role_assignment" "dev_appinsights_contributor" {
  scope                = var.appinsights_id
  role_definition_name = "Application Insights Component Contributor"
  principal_id         = var.developer_object_id
}

# Log Analytics Workspace — KQL queries against diagnostics.
resource "azurerm_role_assignment" "dev_law_reader" {
  scope                = var.law_id
  role_definition_name = "Log Analytics Reader"
  principal_id         = var.developer_object_id
}

# =============================================================================
# App service principal RBAC — mirrors the developer roles so the workshop
# API can authenticate via client_id/client_secret env vars (no user login).
# =============================================================================

resource "azurerm_role_assignment" "app_foundry_cognitive_services_user" {
  scope                = var.foundry_resource_id
  role_definition_name = "Cognitive Services User"
  principal_id         = var.app_object_id
}

resource "azurerm_role_assignment" "app_foundry_cu_contributor" {
  scope                = var.foundry_resource_id
  role_definition_name = "Cognitive Services Content Understanding Contributor"
  principal_id         = var.app_object_id
}

resource "azurerm_role_assignment" "app_foundry_openai_user" {
  scope                = var.foundry_resource_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = var.app_object_id
}

resource "azurerm_role_assignment" "app_project_ai_developer" {
  scope                = var.foundry_project_id
  role_definition_name = "Azure AI Developer"
  principal_id         = var.app_object_id
}
