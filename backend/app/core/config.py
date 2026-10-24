import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH)

# Application
PORT = int(os.getenv("PORT", "8000"))

# Authentication
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = "https://ai26s-master-service.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT = "AI26S-Master-gpt-4o"
AZURE_OPENAI_API_VERSION = "2024-12-01-preview"

# Azure Key Vault
KEY_VAULT_URL = "https://teambkv.vault.azure.net/"
AZURE_OPENAI_API_KEY_SECRET_NAME = "azure-openai-api-key"

credential = DefaultAzureCredential()
secret_client = SecretClient(
    vault_url=KEY_VAULT_URL,
    credential=credential,
)


def get_azure_openai_api_key():
    return secret_client.get_secret(AZURE_OPENAI_API_KEY_SECRET_NAME).value


# Azure Blob Storage
AZURE_STORAGE_ACCOUNT_URL = os.getenv(
    "AZURE_STORAGE_ACCOUNT_URL",
    "https://teambml4703127486.blob.core.windows.net",
)

# Frontend / CORS
FRONTEND_ORIGIN = os.getenv(
    "FRONTEND_ORIGIN",
    "http://localhost:5173",
)

# Refresh token cookie
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/auth"
REFRESH_COOKIE_SAMESITE = "lax"
REFRESH_COOKIE_SECURE = os.getenv("REFRESH_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
