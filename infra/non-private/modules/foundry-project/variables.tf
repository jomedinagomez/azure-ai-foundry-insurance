variable "location" {
  description = "Azure region."
  type        = string
}

variable "project_name" {
  description = "Foundry project resource name (alphanumeric + hyphens)."
  type        = string
}

variable "project_display_name" {
  description = "Foundry project display name."
  type        = string
}

variable "foundry_resource_id" {
  description = "Foundry AI Services account resource ID (parent)."
  type        = string
}

variable "appinsights_id" {
  description = "Application Insights resource ID for the resource-level connection."
  type        = string
}

variable "appinsights_connection_string" {
  description = "Application Insights connection string (credential for the resource-level connection)."
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
