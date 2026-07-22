---
title: antispam.bot
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8080
pinned: false
license: mit
tags:
  - telegram
  - anti-spam
  - ilang
  - chatbot
---

<div align="center">

# 🛡️ antispam.bot

**The AI guardian that keeps your Telegram groups clean — and actually answers your questions.**

Open source (MIT), zero config, self-hostable — the **TelegramGuard** project.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Powered by I-Lang](https://img.shields.io/badge/powered%20by-I--Lang%20Spec-blueviolet)](https://ilang.ai)
[![AI: OpenAI-compatible](https://img.shields.io/badge/AI-OpenAI--compatible-06D6A0)](#self-host)

**[English](README.md)** · **[中文](README_CN.md)** · **[antispam.bot](https://antispam.bot)**

</div>

---

## Add it to your group (zero setup)

Add the official bot — no install, no config, no cost.

### → [@iLangGuardBot](https://t.me/iLangGuardBot)

1. Search `@iLangGuardBot` on Telegram
2. Add it to your group
3. Give it admin — **delete messages** + **ban users**
4. Done. Spam is cleaned automatically; @ it anytime with a question.

You can also DM it directly for AI chat.

---

## What it does

**🚫 Anti-Spam** — Catches ads, scams, crypto & gambling spam. Sees through Unicode lookalikes, full-width and zero-width tricks, emoji stuffing and slang. A zero-cost pre-filter kills the obvious stuff before it ever reaches the AI, and repeat-flooding is caught with no AI call at all.

**👁️ Vision** — Reads images and video thumbnails to catch image-based ads and QR-code scams. In chat, it reads the story behind a photo, not just the pixels.

**💬 Chat** — @ it in any group or DM it privately. Multilingual, auto-detects your language. Ask it anything and get a clear, useful answer — factual on sensitive topics, with sensible boundaries on genuinely harmful ones.

---

## Self-Host

Bring any **OpenAI-compatible** AI provider — [SiliconFlow](https://cloud.siliconflow.cn) (default), OpenAI, DeepSeek, or a local model. You need two things:

- **Bot Token** — [@BotFather](https://t.me/BotFather) → `/newbot`
- **AI API Key** — from your provider (default targets SiliconFlow)

### Option 1 — VPS (one command)

```bash
curl -sL https://raw.githubusercontent.com/ilang-ai/TelegramGuard/main/install.sh | sudo bash
```

Clones, installs dependencies, prompts for your two keys, and runs as a systemd service. Manage it with:

```bash
systemctl status telegramguard     # status
systemctl restart telegramguard    # restart
journalctl -u telegramguard -f     # live logs
```

### Option 2 — HuggingFace Space (free, no server)

1. Fork this repo
2. Create a [HuggingFace Space](https://huggingface.co/new-space) → Docker SDK → Blank
3. GitHub repo → Settings → Secrets → add `HF_TOKEN` (your HF write token)
4. HF Space → Settings → Secrets → add `BOT_TOKEN` + `AI_API_KEY`
5. HF Space → Settings → enable **persistent storage** so `/data` (the SQLite DB) is writable — or add a `DB_PATH` secret pointing somewhere writable
6. Push to GitHub — it auto-deploys to the Space

### Option 3 — Manual

```bash
git clone https://github.com/ilang-ai/TelegramGuard.git
cd TelegramGuard
pip install -r requirements.txt
cp .env.example .env         # fill in BOT_TOKEN + AI_API_KEY
set -a; source .env; set +a  # load .env into the environment
python bot.py
```

After creating your bot, send to [@BotFather](https://t.me/BotFather): `/setjoingroups → Enable` and `/setprivacy → Disable` (so it can see group messages).

### Configuration

Everything is set via environment variables — see [`.env.example`](.env.example):

| Variable | Default | Purpose |
|----------|---------|---------|
| `BOT_TOKEN` | *(required)* | Telegram bot token |
| `AI_API_KEY` | *(required)* | OpenAI-compatible API key |
| `AI_BASE_URL` | `https://api.siliconflow.cn/v1` | Provider endpoint |
| `AI_MODEL` | `deepseek-ai/DeepSeek-V4-Flash` | Text model |
| `AI_VISION_MODELS` | `Qwen/Qwen3-VL-30B…` | Vision fallback chain (comma-separated) |
| `AI_AUDIO_MODEL` | `Qwen/Qwen3-Omni-30B-A3B-Instruct` | Voice-message model |
| `AI_IMAGE_MAX_WIDTH` | `600` | Downscale width before vision calls |
| `LEXICON_HARD_THRESHOLD` | `6` | Slang pre-filter strictness (higher = stricter) |

---

## Customize the AI

The bot's brain lives in plain `.ilang` files — [I-Lang Prompt Spec](https://ilang.ai), where each `::GENE` defines a behavior.

```
prompts_demo/
├── persona.ilang     how it thinks + how it talks
├── antispam.ilang    what counts as spam
└── vision.ilang      how it reads images
```

```
::GENE_IMMUTABLE{S002, T:RUTHLESS_RED_TEAM, A:FLATTER⇒FAIL, G:ALL, Θ:ALWAYS}
# Show it a plan and it hunts the fatal flaw instead of praising.

::GENE_MUTABLE{P002, T:CONCISE, G:ALL, Θ:ALWAYS}
# 2-3 sentences. Answer first, detail after, zero filler.

::IMMUNE{SPAM, DETECT_THEN_NUKE}
# Ads / scams / flooding → delete + strike, see through evasion.
```

Change the genes, change the bot. To customize: copy `prompts_demo/` to `prompts/` (loaded first) and edit.

**[Learn I-Lang Prompt Spec →](https://ilang.ai)**

---

## Architecture

```
TelegramGuard/
├── bot.py                 Entry — handlers (group · private · events)
├── config.py              Env config
├── install.sh             One-command VPS installer
├── Dockerfile             Container build
├── modules/
│   ├── ai_provider.py     OpenAI-compatible AI layer (text · vision · audio)
│   ├── chat.py            Prompt orchestration (loads .ilang)
│   ├── prefilter.py       Zero-cost spam pre-filter + triage
│   ├── lexicon.py         Slang / evasion normalization + scoring
│   ├── ilang_judge.py     I-Lang decision function
│   ├── admin.py           Group admin
│   ├── db.py              Shared SQLite + async lock
│   └── database.py        Schema
└── prompts_demo/          AI personality (.ilang files)
```

---

<div align="center">

Built with **[I-Lang Prompt Spec](https://ilang.ai)** — structured AI instructions as genetic code.

[![Spec](https://img.shields.io/badge/spec-ilang--ai/ilang--spec-black?logo=github)](https://github.com/ilang-ai/ilang-spec)
[![Web](https://img.shields.io/badge/web-ilang.ai-blue)](https://ilang.ai)
[![HF](https://img.shields.io/badge/HF-i--Lang-yellow?logo=huggingface)](https://huggingface.co/i-Lang)

MIT · © [iLang Inc.](https://eastsoft.com) · [antispam.bot](https://antispam.bot) · [ilang.ai](https://ilang.ai)

</div>
