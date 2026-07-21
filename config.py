import os

# Telegram Bot
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# AI provider — OpenAI-compatible (SiliconFlow / OpenAI / DeepSeek / local vLLM / any relay)
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.siliconflow.cn/v1")
AI_MODEL = os.environ.get("AI_MODEL", "deepseek-ai/DeepSeek-V4-Flash")
AI_VISION_MODELS = os.environ.get(
    "AI_VISION_MODELS",
    "Qwen/Qwen3-VL-30B-A3B-Instruct,Qwen/Qwen3-VL-32B-Instruct,Qwen/Qwen3-VL-8B-Instruct",
)
AI_AUDIO_MODEL = os.environ.get("AI_AUDIO_MODEL", "Qwen/Qwen3-Omni-30B-A3B-Instruct")
AI_IMAGE_MAX_WIDTH = int(os.environ.get("AI_IMAGE_MAX_WIDTH", "600"))

# Database
DB_PATH = os.environ.get("DB_PATH", "/data/bot.db")

# Anti-spam
SPAM_NEWUSER_COOLDOWN = int(os.environ.get("SPAM_NEWUSER_COOLDOWN", "300"))
SPAM_REPEAT_THRESHOLD = int(os.environ.get("SPAM_REPEAT_THRESHOLD", "3"))
SPAM_REPEAT_WINDOW = int(os.environ.get("SPAM_REPEAT_WINDOW", "300"))

# Admin user ID (auto-detected from first /start)
ADMIN_USER_ID = None
