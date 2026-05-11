# Workshop App

Local-only workshop shell. Today: a single **Compare** tab for side-by-side
Azure Document Intelligence vs. Azure AI Content Understanding on the same
file. Future tabs (SOV extraction, insurance scenarios) plug into the same
shell.

## Layout

```
apps/workshop/
├── web/      React (CRA + Fluent UI) frontend
└── api/      FastAPI standalone backend (no Cosmos / ServiceBus / AppConfig)
```

## Prerequisites

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) (`winget install astral-sh.uv`)
- Node.js 18+
- Azure CLI signed in: `az login`
- An Azure AI Foundry (or Cognitive Services) endpoint with both
  Document Intelligence and Content Understanding available
- Your signed-in identity needs `Cognitive Services User` (or stronger) on
  that resource

## One-time setup (from repo root)

```powershell
cd <repo-root>
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
```

This creates a single `.venv/` at the repo root used by every Python entry
point in the repo (workshop API, SOV notebooks, audit scripts).

## Run the API

```powershell
cd apps/workshop/api
copy .env.example .env
# Edit .env: set APP_CONTENT_UNDERSTANDING_ENDPOINT to your Foundry/Cognitive Services endpoint
az login
..\..\..\.venv\Scripts\Activate.ps1
python standalone_api.py
```

API serves on `http://localhost:8000`. Smoke test:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/analyzer-compare/analyzers
```

## Run the Web

In a second terminal:

```powershell
cd apps/workshop/web
npm install
copy .env.example .env
npm start
```

Web serves on `http://localhost:3000` and proxies API calls to
`REACT_APP_API_BASE_URL` (default `http://localhost:8000`).

Open `http://localhost:3000`, pick analyzers from the DI and CU dropdowns,
upload a file, run.

## Adding a new tab

Future features (e.g. SOV extraction, insurance) follow the same pattern:

**API** — add a router under `api/app/routers/<feature>.py` and register it
in `standalone_api.py`:

```python
from app.routers import analyzer_compare, my_feature
app.include_router(my_feature.router)
```

**Web** — add:
- `web/src/Pages/<Feature>Page.tsx`
- A route entry in `web/src/App.tsx`
- A tab entry in `web/src/Components/Header/Header.tsx`
- A service module under `web/src/services/<feature>Service.ts`

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| API: `401` from analyzer call | Not signed in / wrong tenant | `az login --tenant <tenant>` |
| API: `403` from analyzer call | Missing data-plane RBAC | Grant `Cognitive Services User` on the endpoint resource |
| Web: dropdowns empty | API not running or CORS blocked | Confirm `http://localhost:8000/health` returns 200 |
| Web: calls fail with mixed-port URL | `.env` not loaded by CRA | Restart `npm start` after editing `.env` |
| API: `APP_CONTENT_UNDERSTANDING_ENDPOINT` missing | `.env` not created | `copy .env.example .env` and edit |

## Notes

- No MSAL — auth flows from the developer's `az login` via
  `DefaultAzureCredential`. Set `APP_ENV=dev` (already the default in
  `.env.example`) to keep that behavior.
- The standalone API trims out the accelerator's Cosmos / ServiceBus /
  App Configuration paths. If you need those later, copy from
  `content-processing-solution-accelerator/src/ContentProcessorAPI/app/`.
