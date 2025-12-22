import os
from pathlib import Path


class Config:
    def __init__(self):
        self.env = self.load_env()
        self.perplexity_api_key = self.env.get("PERPLEXITY_API_KEY")
        self.discord_webhook_url = self.env.get("DISCORD_WEBHOOK_URL")
        self.telegram_bot_token = self.env.get("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = self.env.get("TELEGRAM_CHAT_ID")

        self.token_file = "infomentor_tokens.json"
        self.output_dir = Path("news")
        self.files_dir = Path("files")
        self.api_base_url = "https://api-im.infomentor.se"
        self.auth_base_url = "https://im.infomentor.se"

    def load_env(self):
        """Simple .env loader that merges with os.environ"""
        env_vars = os.environ.copy()
        env_file = Path(".env")
        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
        return env_vars
