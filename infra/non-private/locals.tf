locals {
  instance = var.instance

  # CAF naming: {type}-{workload}-{env}-{instance}
  resource_group_name = "rg-${var.project_name}-${var.environment}-${local.instance}"

  # AI Services / Foundry account name (must be globally unique).
  foundry_name = "ais-${var.project_name}-${var.environment}-${local.instance}"

  # Foundry project: resource name (alphanumeric + hyphens) and display name.
  project_resource_name = "proj-${var.project_name}-${var.environment}-${local.instance}"
  project_display_name  = "Insurance Workshop"

  # App registration display name.
  app_registration_display_name = "sp-${var.project_name}-${var.environment}-${local.instance}"

  # Observability.
  appinsights_name = "appi-${var.project_name}-${var.environment}-${local.instance}"
  law_name         = "log-${var.project_name}-${var.environment}-${local.instance}"

  common_tags = merge(var.tags, {
    environment = var.environment
    region      = var.region
  })

  # Developer object_id to receive RBAC. Falls back to the signed-in principal.
  effective_user_object_id = coalesce(var.user_object_id, data.azuread_client_config.current.object_id)
}
