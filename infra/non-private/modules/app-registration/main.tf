resource "azuread_application" "this" {
  display_name = var.display_name
  tags         = var.tags
}

resource "azuread_service_principal" "this" {
  client_id = azuread_application.this.client_id
  tags      = var.tags
}

# Rotate the secret when secret_rotation_days elapses.
resource "time_rotating" "secret" {
  rotation_days = var.secret_rotation_days
}

resource "azuread_application_password" "this" {
  application_id = azuread_application.this.id
  display_name   = "terraform-managed"
  rotate_when_changed = {
    rotation = time_rotating.secret.id
  }
}

# Let Entra ID replicate the new SP before any RBAC assignments downstream
# depend on its object_id.
resource "time_sleep" "wait_sp" {
  depends_on      = [azuread_service_principal.this]
  create_duration = "30s"
}
