########## Foundry project ##########

resource "azapi_resource" "project" {
  type                      = "Microsoft.CognitiveServices/accounts/projects@2025-10-01-preview"
  name                      = var.project_name
  location                  = var.location
  parent_id                 = var.foundry_resource_id
  schema_validation_enabled = false

  identity {
    type = "SystemAssigned"
  }

  body = {
    sku = {
      name = "S0"
    }
    properties = {
      displayName = var.project_display_name
      description = "Insurance Workshop — Content Understanding demos (SOV, SEC, Pro Mode)."
    }
  }

  response_export_values = [
    "identity.principalId",
    "properties.internalId",
  ]

  tags = var.tags
}

# Wait for the project SMI to replicate through Entra ID.
resource "time_sleep" "wait_project_identities" {
  depends_on      = [azapi_resource.project]
  create_duration = "10s"
}

########## Resource-level App Insights connection ##########
# This connection has to live at the ACCOUNT level (not the project) due to a
# Foundry service behavior, but it must be created after the project exists.

resource "azapi_resource" "conn_resource_appinsights" {
  depends_on = [azapi_resource.project]

  type                      = "Microsoft.CognitiveServices/accounts/connections@2025-10-01-preview"
  name                      = "appinsights-connection"
  parent_id                 = var.foundry_resource_id
  schema_validation_enabled = false

  body = {
    properties = {
      category      = "AppInsights"
      isSharedToAll = true
      target        = var.appinsights_id
      authType      = "ApiKey"
      credentials = {
        key = var.appinsights_connection_string
      }
      metadata = {
        ApiType    = "Azure"
        ResourceId = var.appinsights_id
      }
    }
  }
}
