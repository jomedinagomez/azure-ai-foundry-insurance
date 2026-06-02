# =============================================================================
# Root main.tf — wires all modules together.
# Dependency chain:
#   app-insights  (no deps)
#   → foundry-resource (needs LAW for diagnostics)
#   → foundry-project  (needs Foundry + AppInsights id/conn-string)
#   → rbac             (needs all of the above)
# =============================================================================

resource "azurerm_resource_group" "rg" {
  name     = local.resource_group_name
  location = var.region
  tags     = local.common_tags
}

module "app_insights" {
  source = "./modules/app-insights"

  resource_group_name = azurerm_resource_group.rg.name
  location            = var.region
  law_name            = local.law_name
  appinsights_name    = local.appinsights_name
  tags                = local.common_tags
}

module "foundry_resource" {
  source = "./modules/foundry-resource"

  resource_group_id          = azurerm_resource_group.rg.id
  resource_group_name        = azurerm_resource_group.rg.name
  location                   = var.region
  foundry_name               = local.foundry_name
  sku                        = var.foundry_sku
  log_analytics_workspace_id = module.app_insights.law_id
  tags                       = local.common_tags

  model_capacity     = var.model_capacity
  embedding_capacity = var.embedding_capacity
  gpt52_version      = var.gpt52_version
  gpt41_version      = var.gpt41_version
  gpt41_mini_version = var.gpt41_mini_version
  embedding_version  = var.embedding_version
}

module "foundry_project" {
  source = "./modules/foundry-project"

  location                      = var.region
  project_name                  = local.project_resource_name
  project_display_name          = local.project_display_name
  foundry_resource_id           = module.foundry_resource.id
  appinsights_id                = module.app_insights.appinsights_id
  appinsights_connection_string = module.app_insights.appinsights_connection_string
  tags                          = local.common_tags
}

module "app_registration" {
  source = "./modules/app-registration"

  display_name = local.app_registration_display_name
  tags         = ["insurance-workshop", var.environment]
}

module "rbac" {
  source = "./modules/rbac"

  developer_object_id      = local.effective_user_object_id
  app_object_id            = module.app_registration.object_id
  foundry_resource_id      = module.foundry_resource.id
  foundry_project_id       = module.foundry_project.id
  appinsights_id           = module.app_insights.appinsights_id
  law_id                   = module.app_insights.law_id
  foundry_smi_principal_id = module.foundry_resource.principal_id
}
