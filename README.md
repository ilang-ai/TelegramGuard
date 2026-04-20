---
license: mit
tags:
  - telegram
  - anti-spam
  - ilang
  - chatbot
---

# I-Lang Guard

AI-powered Telegram group guardian. Anti-spam, vision, chat — all driven by [I-Lang Prompt Spec](https://github.com/ilang-ai/ilang-spec).

## What It Does

- **Anti-spam**: AI detects ads, scams, political content, porn, and repeat flooding. Deletes messages and bans spammers automatically.
- **Vision**: Understands images and video thumbnails. Catches image-based spam too.
- **Chat**: @ the bot in any group for AI conversation.
- **Zero config**: Add to group → grant admin permissions → done.

## Deploy Your Own (3 Steps)

### Option A: HuggingFace Space (Free, Zero Server)

1. Fork this repo
2. Create a [HuggingFace Space](https://huggingface.co/new-space) (Docker SDK)
3. Add secrets in Space Settings:

| Secret | How to get it |
|--------|--------------|
| `BOT_TOKEN` | Talk to [@BotFather](https://t.me/BotFather) on Telegram |
| `GEMINI_API_KEY` | Free at [aistudio.google.com](https://aistudio.google.com) |

### Option B: VPS

```bash
git clone https://github.com/ilang-ai/TelegramGuard.git
cd TelegramGuard
pip install -r requirements.txt
export BOT_TOKEN="your-token"
export GEMINI_API_KEY="your-key"
python bot.py
```

## Customize Your Bot

All prompts live in `prompts_demo/` as `.ilang` files:

| File | Controls |
|------|----------|
| `persona.ilang` | Bot personality, tone, rules |
| `antispam.ilang` | What counts as spam |
| `vision.ilang` | How to read images |

To customize: copy `prompts_demo/` to `prompts/`, edit the `.ilang` files. The bot loads `prompts/` first, falls back to `prompts_demo/`.

Prompts use [I-Lang Prompt Spec](https://github.com/ilang-ai/ilang-spec) — a structured format for AI instructions using GENE framework, IMMUNE rules, and layered architecture. Learn more at [ilang.ai](https://ilang.ai).

## Architecture

```
bot.py              Main handler
modules/
  chat.py           AI calls (loads .ilang prompts)
  db.py             Single shared SQLite connection
  database.py       Schema
  admin.py          Group admin helpers
prompts_demo/       Open-source demo prompts (.ilang)
prompts/            Your custom prompts (.gitignore'd)
```

## BotFather Setup

After creating your bot, send these to [@BotFather](https://t.me/BotFather):

```
/setjoingroups → Enable
/setprivacy → Disable (so bot can see all group messages)
```

## License

MIT

---

Powered by [I-Lang Prompt Spec](https://ilang.ai) | [Eastsoft Inc.](https://eastsoft.com)
