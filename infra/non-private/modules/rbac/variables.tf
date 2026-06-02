variable "developer_object_id" {
  description = "Entra ID object ID of the developer receiving RBAC roles."
  type        = string
}

variable "foundry_resource_id" {
  description = "Foundry AI Services account resource ID."
  type        = string
}

variable "foundry_project_id" {
  description = "Foundry project resource ID."
  type        = string
}

variable "appinsights_id" {
  description = "Application Insights resource ID."
  type        = string
}

variable "law_id" {
  description = "Log Analytics Workspace resource ID."
  type        = string
}

variable "foundry_smi_principal_id" {
  description = <<-EOT
    Foundry AI Services system-assigned managed identity principal ID. Accepted
    for forward compatibility (e.g. BYO Storage / Cosmos / Search additions).
    No role assignments are emitted today because the workshop has no BYO data
    plane.
  EOT
  type        = string
}

variable "app_object_id" {
  description = <<-EOT
    Service principal object ID for the workshop app (Terraform-created in the
    app-registration module). Receives the same Foundry data-plane roles as the
    developer so the API can authenticate via client_id/client_secret env vars
    instead of `az login`.
  EOT
  type        = string
}
