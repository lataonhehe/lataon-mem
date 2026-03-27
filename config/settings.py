import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.getenv("MODEL", "anthropic/claude-sonnet-4-5")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN chưa được set trong .env")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY chưa được set trong .env")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL chưa được set trong .env")
