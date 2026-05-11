"""
Standalone runner for the Analyzer Compare API.
Does not require Azure App Configuration — reads settings directly from
environment variables (or a local .env file in this same directory).

Required environment variables:
  APP_CONTENT_UNDERSTANDING_ENDPOINT  – e.g. https://<your-content-understanding-endpoint>.cognitiveservices.azure.com/
  APP_ENV                             – set to "dev" to use DefaultAzureCredential (Azure CLI)

Usage:
  set APP_CONTENT_UNDERSTANDING_ENDPOINT=https://<your-content-understanding-endpoint>.cognitiveservices.azure.com/
  set APP_ENV=dev
  python standalone_api.py
"""

import os
import sys

# Ensure the package root is on sys.path so `from helpers.xxx` imports work
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

# Prefer repo-root .env so the same config powers the workshop API, the SOV
# notebooks, and any feedback/research notebooks. Fall back to api/.env.
_HERE = os.path.dirname(__file__)
_ROOT_ENV = os.path.join(_HERE, "..", "..", "..", ".env")
if os.path.exists(_ROOT_ENV):
    load_dotenv(_ROOT_ENV)
else:
    load_dotenv(os.path.join(_HERE, ".env"))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analyzer_compare, pipelines, sov

app = FastAPI(title="Analyzer Compare API", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyzer_compare.router)
app.include_router(sov.router)
app.include_router(pipelines.router)


@app.get("/health")
def health():
    return {"message": "I'm alive!"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "standalone_api:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_dirs=[os.path.join(os.path.dirname(__file__), "app"),
                     os.path.join(os.path.dirname(__file__), "helpers")],
    )
