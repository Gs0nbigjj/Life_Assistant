from dotenv import load_dotenv
from pathlib import Path
import os
from datetime import timezone, timedelta

BASE_DIR = Path(__file__).resolve().parent
COGS_DIR = os.path.join(BASE_DIR, "cogs")

ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

GPT_API = os.getenv("GPT_API")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("Database URL not found in environment")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
FUGLE_TOKEN = os.getenv("FUGLE_TOKEN")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RENDER = os.getenv("RENDER")

FONT_PATH = os.path.join(BASE_DIR, "jf-openhuninn-1.1.ttf")
TW_TZ = timezone(timedelta(hours=8))

class APIKeyPool:
    def __init__(self, env_variable_name: str):
        keys_string = os.getenv(env_variable_name, "")
        self.keys = [k.strip() for k in keys_string.split(",") if k.strip()]
        self.current_index = 0

    @property
    def current_key(self) -> str:
        if not self.keys:
            return ""
        return self.keys[self.current_index]

    def switch_to_next(self) -> bool:
        if self.current_index < len(self.keys) - 1:
            self.current_index += 1
            return True
        return False

OPENROUTER_POOL = APIKeyPool("OPENROUTER_API_KEYS")
