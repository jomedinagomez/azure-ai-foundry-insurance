variable "resource_group_id" {
  description = "Resource group ID."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "foundry_name" {
  description = "Name for the AI Services (Foundry) resource."
  type        = string
}

variable "sku" {
  description = "SKU for the AI Services resource."
  type        = string
  default     = "S0"
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID for diagnostics."
  type        = string
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}

# Model deployment knobs.
variable "model_capacity" {
  description = "Default capacity (TPM × 1k) for chat-model deployments."
  type        = number
  default     = 100
}

variable "embedding_capacity" {
  description = "Capacity for the text-embedding-3-large deployment."
  type        = number
  default     = 300
}

variable "gpt52_version" {
  description = "Model version for gpt-5.2."
  type        = string
}

variable "gpt41_version" {
  description = "Model version for gpt-4.1."
  type        = string
}

variable "gpt41_mini_version" {
  description = "Model version for gpt-4.1-mini."
  type        = string
}

variable "embedding_version" {
  description = "Model version for text-embedding-3-large."
  type        = string
}
