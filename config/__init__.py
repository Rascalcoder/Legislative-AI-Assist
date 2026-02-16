"""
Configuration loader - reads JSON config files + .env for API keys.
All application config comes from JSON. Only API keys come from .env.

Usage:
    from config import cfg
    cfg.models["roles"]["light"]["model"]  # "gpt-4o-mini"
    cfg.get_api_key("OPENAI_API_KEY")      # reads from .env
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_CONFIG_DIR = Path(__file__).parent


def _load_json(filename: str) -> dict:
    filepath = _CONFIG_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


class Config:
    """Central configuration - JSON files + environment variables."""

    def __init__(self):
        self.models: dict = _load_json("models.json")
        self.search: dict = _load_json("search.json")
        self.sources: dict = _load_json("sources.json")
        self.prompts: dict = _load_json("prompts.json")

    def get_api_key(self, env_var: str) -> str:
        """Get API key from environment variable."""
        val = os.getenv(env_var)
        if not val:
            raise ValueError(f"Missing environment variable: {env_var}")
        return val

    @property
    def supabase_url(self) -> str:
        return self.get_api_key("SUPABASE_URL")

    @property
    def supabase_key(self) -> str:
        return self.get_api_key("SUPABASE_SERVICE_KEY")

    def reload(self):
        """Reload all JSON config files (for runtime updates)."""
        self.models = _load_json("models.json")
        self.search = _load_json("search.json")
        self.sources = _load_json("sources.json")
        self.prompts = _load_json("prompts.json")


cfg = Config()
