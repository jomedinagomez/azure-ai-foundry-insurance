variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}

variable "region" {
  description = <<-EOT
    Azure region for all resources. Must be one of the three regions that
    currently support the Content Understanding pro mode preview API
    (api-version=2025-05-01-preview): westus, swedencentral, australiaeast.
    See: https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/language-region-support#preview-api-2025-05-01-preview
  EOT
  type        = string
  default     = "westus"

  validation {
    condition     = contains(["westus", "swedencentral", "australiaeast"], var.region)
    error_message = "Content Understanding pro mode is only available in westus, swedencentral, or australiaeast."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project short name used for CAF resource naming."
  type        = string
  default     = "insurance-workshop"
}

variable "instance" {
  description = "Instance number for parallel deployments (e.g. 01, 02)."
  type        = string
  default     = "01"
}

variable "user_object_id" {
  description = <<-EOT
    Entra ID object ID of the developer that should receive RBAC roles. If
    null, defaults to the currently authenticated principal (the object ID
    behind your `az login` session).
  EOT
  type        = string
  default     = null
  nullable    = true
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default = {
    project     = "insurance-workshop"
    environment = "dev"
    managed_by  = "terraform"
  }
}

variable "foundry_sku" {
  description = "SKU for the Foundry AI Services account."
  type        = string
  default     = "S0"
}

variable "model_capacity" {
  description = "Default capacity (TPM × 1k) for each model deployment."
  type        = number
  default     = 100
}

variable "embedding_capacity" {
  description = "Capacity for the text-embedding-3-large deployment (typically higher than chat models)."
  type        = number
  default     = 300
}

variable "gpt52_version" {
  description = "Model version for gpt-5.2."
  type        = string
  default     = "2025-12-11"
}

variable "gpt41_version" {
  description = "Model version for gpt-4.1."
  type        = string
  default     = "2025-04-14"
}

variable "gpt41_mini_version" {
  description = "Model version for gpt-4.1-mini."
  type        = string
  default     = "2025-04-14"
}

variable "embedding_version" {
  description = "Model version for text-embedding-3-large."
  type        = string
  default     = "1"
}
