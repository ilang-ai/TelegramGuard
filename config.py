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

# Chinese-slang lexicon hard-hit threshold (prefilter Layer 2.5). Higher = stricter.
LEXICON_HARD_THRESHOLD = int(os.environ.get("LEXICON_HARD_THRESHOLD", "6"))

# Probe ("check-in") detection. Mark-only layer: it never bans, it only starts
# silently deleting once a member has been flagged this many times...
PROBE_FLAG_DELETE = int(os.environ.get("PROBE_FLAG_DELETE", "2"))
# ...within this rolling window (hours). Flags older than the window reset to 1,
# so a real person posting one such message a day is never permanently silenced.
PROBE_WINDOW_HOURS = int(os.environ.get("PROBE_WINDOW_HOURS", "24"))

# How much of an over-long message the spam judge sees. The text is clipped
# head + tail (never head only), so an ad appended to the end of a long paste
# still lands inside the judged range.
JUDGE_TEXT_LIMIT = int(os.environ.get("JUDGE_TEXT_LIMIT", "1800"))
JUDGE_CAPTION_LIMIT = int(os.environ.get("JUDGE_CAPTION_LIMIT", "900"))

# Public group commands reply with reply_text, which bumps the triggering
# message to the top of the chat. Without a cooldown anyone can spam a command
# and have the bot repeatedly bump their own ad. Seconds, per chat, non-admins
# only — admins and private chats are never limited.
GROUP_CMD_COOLDOWN = int(os.environ.get("GROUP_CMD_COOLDOWN", "60"))

# Admin user ID (auto-detected from first /start)
ADMIN_USER_ID = None
