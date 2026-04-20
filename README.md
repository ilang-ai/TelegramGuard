---
title: TelegramGuard
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: static
pinned: false
license: mit
tags:
  - telegram
  - anti-spam
  - ilang
  - chatbot
---

<div align="center">

# 🛡️ TelegramGuard

**AI group guardian that actually answers your questions.**

Anti-spam. Vision. Chat. No topic off-limits.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Powered by I-Lang](https://img.shields.io/badge/powered%20by-I--Lang%20Spec-blueviolet)](https://ilang.ai)
[![Gemini](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-4285F4)](https://aistudio.google.com)

**[English](README.md)** | **[中文](README_CN.md)**

</div>

---

## Use It Now (Zero Setup)

Add the official bot to your Telegram group. No install, no config, no cost.

**[@iLangGuardBot](https://t.me/iLangGuardBot)**

1. Open Telegram, search `@iLangGuardBot`
2. Add it to your group
3. Grant admin permissions (delete messages + ban users)
4. Done. Spam protection is automatic.

You can also DM the bot directly for AI chat.

---

## What It Does

**Anti-Spam** — AI three-step analysis detects ads, scams, crypto spam, porn, political propaganda. Sees through Unicode tricks, emoji stuffing, homophone substitution. Catches repeat flooding (same message 3+ times) with zero AI cost. Bans and deletes all recent messages in parallel.

**Vision** — Reads images and video thumbnails. Catches image spam. In chat mode, analyzes what's really happening in a photo, not just describing objects.

**Chat** — @ the bot in any group or DM privately. Multilingual, auto-detects your language. Finance, tech, relationships, culture, anything. Answers first, lectures never.

**Three-Step Method for Sensitive Topics** — Most bots refuse. TelegramGuard uses a different approach:

| Step | What happens |
|------|-------------|
| **Insider Risks** | Shares what actually goes wrong: scams, traps, consequences |
| **Reality Check** | Asks if you're curious or serious, no judgment |
| **Direction** | Gives enough info to make smart decisions |

---

## Host Your Own

### Option 1: VPS (One Command)

```bash
curl -sL https://raw.githubusercontent.com/ilang-ai/TelegramGuard/main/install.sh | sudo bash
```

The script handles everything: clone, dependencies, token setup, systemd service, auto-start.

You need two things (both free):
- **Bot Token** — open Telegram → [@BotFather](https://t.me/BotFather) → `/newbot`
- **Gemini API Key** — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

After install:
```bash
systemctl status telegramguard     # check status
systemctl restart telegramguard    # restart
journalctl -u telegramguard -f    # live logs
```

### Option 2: HuggingFace Space (Free, No Server)

1. Fork this repo
2. Create a [HuggingFace Space](https://huggingface.co/new-space) → Docker SDK → Blank
3. GitHub repo Settings → Secrets → add `HF_TOKEN` (your HF write token)
4. HF Space Settings → Secrets → add `BOT_TOKEN` + `GEMINI_API_KEY`
5. Push to GitHub triggers auto-deploy to HF

### Option 3: Manual

```bash
git clone https://github.com/ilang-ai/TelegramGuard.git
cd TelegramGuard
pip install -r requirements.txt
export BOT_TOKEN="your-token"
export GEMINI_API_KEY="your-key"
python bot.py
```

---

## Customize the AI

The bot's brain lives in `.ilang` files using [I-Lang Prompt Spec](https://ilang.ai):

```
prompts_demo/
├── persona.ilang     How it thinks + how it talks
├── antispam.ilang    What counts as spam
└── vision.ilang      How it reads images
```

Each file contains `::GENE` definitions that control behavior:

```
::GENE_IMMUTABLE{S001, T:ANTI_COLLAPSE, A:MORAL_PANIC⇒LETHAL, G:ALL, Θ:ALWAYS}
# When user raises grey topics: don't panic, analyze objectively.

::IMMUNE{RISKY_OR_ILLEGAL, THREE_STEP_RESPONSE}
# Step 1: Insider risks  Step 2: Reality check  Step 3: Direction
```

Change the genes, change the bot. To customize: copy `prompts_demo/` to `prompts/`, edit. The bot loads `prompts/` first.

**[Learn I-Lang Prompt Spec →](https://ilang.ai)**

---

## BotFather Setup

After creating your bot, send to [@BotFather](https://t.me/BotFather):

```
/setjoingroups  → Enable
/setprivacy     → Disable
```

---

## Architecture

```
TelegramGuard/
├── bot.py                 Core (group + private + events)
├── config.py              Env vars
├── install.sh             One-line VPS installer
├── Dockerfile             HF Space deployment
├── modules/
│   ├── chat.py            AI engine (loads .ilang prompts)
│   ├── db.py              Shared SQLite + async lock
│   ├── database.py        Schema
│   └── admin.py           Group admin
└── prompts_demo/          AI personality (.ilang files)
```

---

<div align="center">

Built with **[I-Lang Prompt Spec](https://ilang.ai)** — structured AI instructions using genetic code.

[![Spec](https://img.shields.io/badge/spec-ilang--ai/ilang--spec-black?logo=github)](https://github.com/ilang-ai/ilang-spec)
[![Web](https://img.shields.io/badge/web-ilang.ai-blue)](https://ilang.ai)
[![HF](https://img.shields.io/badge/HF-i--Lang-yellow?logo=huggingface)](https://huggingface.co/i-Lang)

MIT | [Eastsoft Inc.](https://eastsoft.com) | [I-Lang Research](https://research.ilang.ai)

</div>
