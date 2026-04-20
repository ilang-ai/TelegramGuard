---
title: TelegramGuard
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
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
[![Deploy on HF](https://img.shields.io/badge/deploy-HuggingFace%20Space-yellow)](https://huggingface.co/spaces/i-Lang/TelegramGuard)
[![Gemini](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-4285F4)](https://aistudio.google.com)

</div>

---

## One-Line Install (VPS)

```bash
curl -sL https://raw.githubusercontent.com/ilang-ai/TelegramGuard/main/install.sh | sudo bash
```

That's it. The script clones, installs, asks for your tokens, creates a system service, and starts.

You need two things (both free):
- **Bot Token** from [@BotFather](https://t.me/BotFather) on Telegram
- **Gemini API Key** from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

---

## What Makes This Different

Most Telegram bots refuse to discuss anything remotely sensitive. TelegramGuard uses a **three-step method** for risky topics:

| Step | What happens |
|------|-------------|
| **Insider Risks** | Shares what actually goes wrong: scams, traps, how people get burned |
| **Reality Check** | Asks if you're curious or serious, no judgment |
| **Direction** | If you persist, gives enough info to stay safe |

This isn't a compliance bot. It's a street-smart friend who's seen things.

Built on [**I-Lang Prompt Spec**](https://ilang.ai), a structured protocol that programs AI behavior using genetic code. The bot's personality lives in `.ilang` files with GENE definitions, IMMUNE response patterns, and a layered SOUL/PUBLIC architecture.

---

## Features

**Anti-Spam** — AI-powered three-step analysis. Detects ads, scams, crypto spam, sexual content, political propaganda. Sees through Unicode tricks, emoji stuffing, and homophone substitution. Catches repeat flooding without AI (pure logic, zero token cost). Bans spammers and deletes all their recent messages in parallel.

**Vision** — Reads images using three-step image analysis: inventory everything in the image, find the subtext, deliver the insight. Catches image-based spam too. Understands video thumbnails.

**Chat** — @ the bot in any group or DM it privately. Multilingual, auto-detects your language. Knows finance, tech, relationships, culture, underground. Answers first, skips the lecture.

**Zero Config** — Add to group. Grant admin permissions. Done. No commands, no setup, no dashboards.

---

## Deploy (Pick One)

### VPS — One Command

```bash
curl -sL https://raw.githubusercontent.com/ilang-ai/TelegramGuard/main/install.sh | sudo bash
```

Manage after install:

```bash
systemctl status telegramguard     # check status
systemctl restart telegramguard    # restart
journalctl -u telegramguard -f    # live logs
```

### HuggingFace Space — Zero Server

1. Fork this repo
2. Create a [HuggingFace Space](https://huggingface.co/new-space) → Docker SDK → Blank
3. Set GitHub Actions secret: `HF_TOKEN` (your HF write token)
4. Set Space secrets: `BOT_TOKEN` + `GEMINI_API_KEY`
5. Push triggers auto-deploy

### Manual

```bash
git clone https://github.com/ilang-ai/TelegramGuard.git
cd TelegramGuard
pip install -r requirements.txt
export BOT_TOKEN="your-token"
export GEMINI_API_KEY="your-key"
python bot.py
```

---

## Customize the AI Personality

The bot's brain lives in three `.ilang` files:

```
prompts_demo/
├── persona.ilang     SOUL (how it thinks) + PUBLIC (how it talks)
├── antispam.ilang    What counts as spam, three-step detection
└── vision.ilang      How to read images, three-step method
```

Open `persona.ilang` — it's a complete tutorial on I-Lang Prompt Spec:

```
::GENE_IMMUTABLE{S001, T:ANTI_COLLAPSE, A:MORAL_PANIC⇒LETHAL, G:ALL, Θ:ALWAYS}
# When user raises extreme or grey topics:
# ¬PANIC(moral_alignment) => HOLD(tension) => COMPUTE(structural_viability)
# Never collapse into safety platitudes.

::IMMUNE{RISKY_OR_ILLEGAL, THREE_STEP_RESPONSE}
# Step 1 — INSIDER RISKS: Share what actually goes wrong
# Step 2 — REALITY CHECK: "Curious or serious?"
# Step 3 — DIRECTION WITH WARNINGS: Give info to stay safe
```

Every `::GENE` defines a behavior. `IMMUTABLE` genes can't be overridden. `MUTABLE` genes adapt to context. `::IMMUNE` patterns handle edge cases. Change the genes, change the bot.

To create your own version: copy `prompts_demo/` to `prompts/` and edit. The bot loads `prompts/` first, falls back to `prompts_demo/`.

**[Learn I-Lang Prompt Spec →](https://ilang.ai)**

---

## Architecture

```
TelegramGuard/
├── bot.py                 Main handler (group + private + events)
├── config.py              Env vars (BOT_TOKEN, GEMINI_API_KEY)
├── install.sh             One-line VPS installer
├── Dockerfile             HuggingFace Space deployment
├── modules/
│   ├── chat.py            AI engine (loads .ilang prompts at startup)
│   ├── db.py              Single shared SQLite connection + async lock
│   ├── database.py        Schema (groups, spam_log, tos_consent)
│   └── admin.py           Group admin helpers
└── prompts_demo/          AI personality in I-Lang Prompt Spec
    ├── persona.ilang      SOUL + PUBLIC + PROPAGATION layers
    ├── antispam.ilang     Three-step spam detection
    └── vision.ilang       Three-step image reading
```

---

## BotFather Setup

After creating your bot with [@BotFather](https://t.me/BotFather):

```
/setjoingroups  → Enable       (allow adding to groups)
/setprivacy     → Disable      (bot can see all group messages for anti-spam)
```

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Runtime | Python 3.11 | Async, universal |
| AI | Gemini 2.5 Flash | Free tier, fast, vision capable |
| Database | SQLite + async lock | Zero setup, single file |
| Prompts | I-Lang Prompt Spec | Structured > natural language |
| Deploy | Docker / systemd | HF Space or any VPS |

---

<div align="center">

**[I-Lang Prompt Spec](https://ilang.ai)** — Structured AI instructions using genetic code.

GENE framework. IMMUNE patterns. SOUL/PUBLIC layers.

One `.ilang` file defines an entire AI personality.

[![GitHub](https://img.shields.io/badge/spec-ilang--ai/ilang--spec-black?logo=github)](https://github.com/ilang-ai/ilang-spec)
[![Website](https://img.shields.io/badge/web-ilang.ai-blue)](https://ilang.ai)
[![HuggingFace](https://img.shields.io/badge/HF-i--Lang-yellow?logo=huggingface)](https://huggingface.co/i-Lang)

MIT | [Eastsoft Inc.](https://eastsoft.com) | [I-Lang Research](https://research.ilang.ai)

</div>
