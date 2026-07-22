<div align="center">

# 🛡️ antispam.bot

**AI-хранитель, который поддерживает чистоту в ваших Telegram-группах — и по-настоящему отвечает на ваши вопросы.**

Открытый исходный код (MIT), нулевая настройка, возможность self-hosting — проект **TelegramGuard**.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Powered by I-Lang](https://img.shields.io/badge/powered%20by-I--Lang%20Spec-blueviolet)](https://ilang.ai)
[![AI: OpenAI-compatible](https://img.shields.io/badge/AI-OpenAI--compatible-06D6A0)](#self-host)

🌐 [English](README.md) · [中文](README_CN.md) · [Русский](README_RU.md) · [Español](README_ES.md) · [العربية](README_AR.md) · [فارسی](README_FA.md)

</div>

---

## Добавьте в свою группу (без настройки)

Добавьте официального бота — без установки, без сервера, бесплатно.

### → [@iLangGuardBot](https://t.me/iLangGuardBot)

1. Найдите `@iLangGuardBot` в Telegram
2. Добавьте его в свою группу
3. Выдайте права администратора — **удаление сообщений** + **блокировка пользователей**
4. Готово. Спам удаляется автоматически; в любой момент упомяните его через @, чтобы задать вопрос.

Ещё ему можно написать напрямую в личные сообщения для общения с AI.

---

## Что он умеет

**🚫 Антиспам** — Ловит рекламу, мошенничество, спам про криптовалюту и азартные игры. Видит насквозь похожие символы Unicode, уловки с полноширинными символами и символами нулевой ширины, нагромождение эмодзи и сленг. Предварительный фильтр с нулевой стоимостью отсекает очевидное ещё до того, как оно дойдёт до AI, а повторный флуд перехватывается вообще без единого обращения к AI.

**👁️ Зрение** — Читает изображения и превью видео, чтобы отлавливать рекламу в картинках и мошенничество с QR-кодами. В переписке он считывает историю за фотографией, а не просто пиксели.

**💬 Чат** — Упомяните его через @ в любой группе или напишите в личку. Многоязычный, автоматически определяет ваш язык. Спросите о чём угодно и получите чёткий, полезный ответ — по существу в чувствительных темах и с разумными границами в по-настоящему опасных.

---

## Self-Host

Подключите любого **OpenAI-совместимого** провайдера AI — [SiliconFlow](https://cloud.siliconflow.cn) (по умолчанию), OpenAI, DeepSeek или локальную модель. Понадобятся две вещи:

- **Bot Token** — [@BotFather](https://t.me/BotFather) → `/newbot`
- **AI API Key** — от вашего провайдера (по умолчанию нацелено на SiliconFlow)

### Вариант 1 — VPS (одна команда)

```bash
curl -sL https://raw.githubusercontent.com/ilang-ai/TelegramGuard/main/install.sh | sudo bash
```

Клонирует репозиторий, ставит зависимости, запрашивает два ваших ключа и запускается как systemd-сервис. Управление:

```bash
systemctl status telegramguard     # status
systemctl restart telegramguard    # restart
journalctl -u telegramguard -f     # live logs
```

### Вариант 2 — HuggingFace Space (бесплатно, без сервера)

1. Сделайте форк этого репозитория
2. Создайте [HuggingFace Space](https://huggingface.co/new-space) → Docker SDK → Blank
3. GitHub-репозиторий → Settings → Secrets → добавьте `HF_TOKEN` (ваш HF write token)
4. HF Space → Settings → Secrets → добавьте `BOT_TOKEN` + `AI_API_KEY`
5. HF Space → Settings → включите **постоянное хранилище (persistent storage)**, чтобы каталог `/data` (база SQLite) был доступен для записи — либо добавьте secret `DB_PATH`, указывающий на путь с правом записи
6. Отправьте изменения в GitHub — деплой в Space произойдёт автоматически

### Вариант 3 — Вручную

```bash
git clone https://github.com/ilang-ai/TelegramGuard.git
cd TelegramGuard
pip install -r requirements.txt
cp .env.example .env         # fill in BOT_TOKEN + AI_API_KEY
set -a; source .env; set +a  # load .env into the environment
python bot.py
```

После создания бота отправьте [@BotFather](https://t.me/BotFather): `/setjoingroups → Enable` и `/setprivacy → Disable` (чтобы он мог видеть сообщения в группе).

### Конфигурация

Всё задаётся через переменные окружения — см. [`.env.example`](.env.example):

| Переменная | Значение по умолчанию | Назначение |
|----------|---------|---------|
| `BOT_TOKEN` | *(required)* | Токен Telegram-бота |
| `AI_API_KEY` | *(required)* | OpenAI-совместимый API-ключ |
| `AI_BASE_URL` | `https://api.siliconflow.cn/v1` | Адрес провайдера |
| `AI_MODEL` | `deepseek-ai/DeepSeek-V4-Flash` | Текстовая модель |
| `AI_VISION_MODELS` | `Qwen/Qwen3-VL-30B…` | Резервная цепочка моделей зрения (через запятую) |
| `AI_AUDIO_MODEL` | `Qwen/Qwen3-Omni-30B-A3B-Instruct` | Модель для голосовых сообщений |
| `AI_IMAGE_MAX_WIDTH` | `600` | Ширина уменьшения изображения перед вызовами зрения |
| `LEXICON_HARD_THRESHOLD` | `6` | Строгость предфильтра сленга (выше = строже) |

---

## Настройка AI

Мозг бота живёт в обычных файлах `.ilang` — [I-Lang Prompt Spec](https://ilang.ai), где каждый `::GENE` определяет поведение.

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

Измените гены — измените бота. Чтобы настроить: скопируйте `prompts_demo/` в `prompts/` (загружается первым) и отредактируйте.

**[Изучить I-Lang Prompt Spec →](https://ilang.ai)**

---

## Архитектура

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

Создано на **[I-Lang Prompt Spec](https://ilang.ai)** — структурированные инструкции для AI как генетический код.

[![Spec](https://img.shields.io/badge/spec-ilang--ai/ilang--spec-black?logo=github)](https://github.com/ilang-ai/ilang-spec)
[![Web](https://img.shields.io/badge/web-ilang.ai-blue)](https://ilang.ai)
[![HF](https://img.shields.io/badge/HF-i--Lang-yellow?logo=huggingface)](https://huggingface.co/i-Lang)

MIT · © [iLang Inc.](https://eastsoft.com) · [antispam.bot](https://antispam.bot) · [ilang.ai](https://ilang.ai)

</div>
