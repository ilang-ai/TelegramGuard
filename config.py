import os

# Telegram Bot
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Gemini AI
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Database
DB_PATH = os.environ.get("DB_PATH", "data/bot.db")

# Anti-spam
SPAM_NEWUSER_COOLDOWN = int(os.environ.get("SPAM_NEWUSER_COOLDOWN", "300"))
SPAM_REPEAT_THRESHOLD = int(os.environ.get("SPAM_REPEAT_THRESHOLD", "3"))
SPAM_REPEAT_WINDOW = int(os.environ.get("SPAM_REPEAT_WINDOW", "300"))

# Admin user ID (auto-detected from first /start)
ADMIN_USER_ID = None
