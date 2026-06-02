# Insurance Workshop infrastructure

Lean Terraform stack that provisions the minimum Azure surface required to
run the workshop's API + UI + notebooks + Pro Mode demos.

## What gets created

| Resource | Module | Purpose |
|---|---|---|
| Resource group | (root) | Container for everything below. |
| Log Analytics Workspace + Application Insights | `modules/app-insights` | Observability + diagnostics sink. |
| Azure AI Foundry account (`Microsoft.CognitiveServices/accounts` kind `AIServices`) | `modules/foundry-resource` | Hosts Content Understanding + Azure OpenAI. |
| `gpt-5.2`, `gpt-4.1`, `gpt-4.1-mini`, `text-embedding-3-large` deployments | `modules/foundry-resource` | Models used by the SOV, SEC, Pro Mode, and analyzer-compare flows. |
| Foundry project + resource-level App Insights connection | `modules/foundry-project` | Required for project-scoped CU calls. |
| RBAC for the signed-in developer | `modules/rbac` | Cognitive Services User / OpenAI User / Azure AI Developer / App Insights Contributor / LAW Reader. |

**Intentionally excluded** (the workshop does not use these): AI Search,
Cosmos DB, Bing grounding, BYO Storage, Key Vault, app registrations,
Container Apps / ACR. Modules are structured so any can be added later.

## Region

Pinned to `westus` by default because that is currently the only region
that supports both:

- **Content Understanding pro mode preview** (`api-version=2025-05-01-preview`)
- **GPT-5.2 deployments** in Azure OpenAI

The region variable validates against the three supported pro-mode regions
(`westus`, `swedencentral`, `australiaeast`). See
[MS Learn — CU region support](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/language-region-support#preview-api-2025-05-01-preview).

## Prerequisites

- Terraform >= 1.10
- Azure CLI logged in: `az login --tenant <your-tenant>`
- `az account set --subscription <your-subscription-id>`
- An object ID with quota for the four model deployments in `westus`. Check with
  `az cognitiveservices usage list --location westus`.

## Usage

```powershell
cd infra/non-private
Copy-Item terraform.tfvars-example terraform.tfvars
# Edit terraform.tfvars: paste subscription_id, optionally pin user_object_id.

terraform init
terraform fmt -recursive
terraform validate
terraform plan
terraform apply
```

On every `terraform apply`, the stack writes the repo-root `.env` to
`../../.env` with:

```
APP_CONTENT_UNDERSTANDING_ENDPOINT=...
APP_ENV=dev
APP_CU_PRO_COMPLETION_DEPLOYMENT=gpt-5.2
APP_CU_COMPLETION_DEPLOYMENT=gpt-4.1-mini
GPT52_MODEL_DEPLOYMENT=gpt-5.2
GPT41_MODEL_DEPLOYMENT=gpt-4.1
GPT41_MINI_MODEL_DEPLOYMENT=gpt-4.1-mini
EMBEDDING_MODEL_DEPLOYMENT=text-embedding-3-large
APPINSIGHTS_CONNECTION_STRING=...
AZURE_SUBSCRIPTION_ID=...
AZURE_TENANT_ID=...
AZURE_RESOURCE_GROUP=...
```

If a `.env` already exists at the repo root, it is backed up to `.env.bak`
before being overwritten.

## After apply

1. Restart the workshop API: `python apps/workshop/api/standalone_api.py`.
2. Open the web UI (`npm start` in `apps/workshop/web/`).
3. Navigate to **Pro Mode** and click **Deploy analyzers** — this registers
   `proClaimsV1` + `proFraudV1` with `auto_policy.pdf` as reference data
   against the new Foundry resource.

## Tear down

```powershell
terraform destroy
```

This deletes the resource group and everything inside, including the
cognitive-account purge (soft-delete is bypassed via the provider feature
flag).
