########## Foundry (AI Services) account ##########

resource "azapi_resource" "foundry" {
  type                      = "Microsoft.CognitiveServices/accounts@2025-10-01-preview"
  name                      = var.foundry_name
  location                  = var.location
  parent_id                 = var.resource_group_id
  schema_validation_enabled = true

  identity {
    type = "SystemAssigned"
  }

  body = {
    kind = "AIServices"
    sku = {
      name = var.sku
    }
    properties = {
      allowProjectManagement        = true
      customSubDomainName           = var.foundry_name
      publicNetworkAccess           = "Enabled"
      disableLocalAuth              = false
      restore                       = false
      restrictOutboundNetworkAccess = false
      networkAcls = {
        defaultAction = "Allow"
      }
    }
  }

  response_export_values = [
    "properties.endpoint",
    "identity.principalId",
  ]

  tags = var.tags

  lifecycle {
    ignore_changes = [body]
  }
}

# Account-level capability host. Project-level hosts require this.
resource "azapi_resource" "account_capability_host" {
  depends_on = [azapi_resource.foundry]

  type                      = "Microsoft.CognitiveServices/accounts/capabilityHosts@2025-04-01-preview"
  name                      = "default"
  parent_id                 = azapi_resource.foundry.id
  schema_validation_enabled = false

  body = {
    properties = {}
  }
}

# Allow the system-assigned identity to replicate through Entra ID before
# any RBAC assignments downstream depend on it.
resource "time_sleep" "wait_smi_foundry" {
  depends_on      = [azapi_resource.foundry]
  create_duration = "10s"
}

########## Model deployments ##########
# Serialized via depends_on so concurrent provisioning doesn't trip TPM
# quota contention. Order: gpt-5.2 → gpt-4.1 → gpt-4.1-mini → embedding.

resource "azurerm_cognitive_deployment" "gpt52" {
  depends_on = [azapi_resource.foundry]

  name                 = "gpt-5.2"
  cognitive_account_id = azapi_resource.foundry.id
  rai_policy_name      = "Microsoft.DefaultV2"

  model {
    format  = "OpenAI"
    name    = "gpt-5.2"
    version = var.gpt52_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = var.model_capacity
  }
}

resource "azurerm_cognitive_deployment" "gpt41" {
  depends_on = [azurerm_cognitive_deployment.gpt52]

  name                 = "gpt-4.1"
  cognitive_account_id = azapi_resource.foundry.id
  rai_policy_name      = "Microsoft.DefaultV2"

  model {
    format  = "OpenAI"
    name    = "gpt-4.1"
    version = var.gpt41_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = var.model_capacity
  }
}

resource "azurerm_cognitive_deployment" "gpt41_mini" {
  depends_on = [azurerm_cognitive_deployment.gpt41]

  name                 = "gpt-4.1-mini"
  cognitive_account_id = azapi_resource.foundry.id
  rai_policy_name      = "Microsoft.DefaultV2"

  model {
    format  = "OpenAI"
    name    = "gpt-4.1-mini"
    version = var.gpt41_mini_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = var.model_capacity
  }
}

resource "azurerm_cognitive_deployment" "embedding" {
  depends_on = [azurerm_cognitive_deployment.gpt41_mini]

  name                 = "text-embedding-3-large"
  cognitive_account_id = azapi_resource.foundry.id
  rai_policy_name      = "Microsoft.DefaultV2"

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-large"
    version = var.embedding_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = var.embedding_capacity
  }
}

########## Diagnostics ##########

resource "azurerm_monitor_diagnostic_setting" "foundry" {
  depends_on = [azapi_resource.foundry]

  name                       = "diag-${var.foundry_name}"
  target_resource_id         = azapi_resource.foundry.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log { category = "Audit" }
  enabled_log { category = "AzureOpenAIRequestUsage" }
  enabled_log { category = "RequestResponse" }
  enabled_log { category = "Trace" }

  enabled_metric { category = "AllMetrics" }
}
