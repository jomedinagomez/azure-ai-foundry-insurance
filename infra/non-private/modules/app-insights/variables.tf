variable "resource_group_name" {
  description = "Resource group name."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "law_name" {
  description = "Name for the Log Analytics Workspace."
  type        = string
}

variable "appinsights_name" {
  description = "Name for Application Insights."
  type        = string
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
