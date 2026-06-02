variable "display_name" {
  description = "Display name for the Entra ID app registration."
  type        = string
}

variable "tags" {
  description = "Tags applied to the app registration."
  type        = list(string)
  default     = []
}

variable "secret_rotation_days" {
  description = "Lifetime in days for the generated client secret."
  type        = number
  default     = 180
}
