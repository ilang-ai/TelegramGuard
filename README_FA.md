<div align="center">

# 🛡️ antispam.bot

**نگهبان هوش مصنوعی که گروه‌های تلگرام شما را پاک نگه می‌دارد — و واقعاً به پرسش‌هایتان پاسخ می‌دهد.**

متن‌باز (MIT)، بدون تنظیمات، قابل میزبانی شخصی — پروژه‌ی **TelegramGuard**.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Powered by I-Lang](https://img.shields.io/badge/powered%20by-I--Lang%20Spec-blueviolet)](https://ilang.ai)
[![AI: OpenAI-compatible](https://img.shields.io/badge/AI-OpenAI--compatible-06D6A0)](#self-host)

🌐 [English](README.md) · [中文](README_CN.md) · [Русский](README_RU.md) · [Español](README_ES.md) · [العربية](README_AR.md) · [فارسی](README_FA.md)

</div>

---

## افزودن به گروه شما (بدون راه‌اندازی)

ربات رسمی را اضافه کنید — بدون نصب، بدون تنظیمات، بدون هزینه.

### → [@iLangGuardBot](https://t.me/iLangGuardBot)

1. در تلگرام `@iLangGuardBot` را جست‌وجو کنید
2. آن را به گروه‌تان اضافه کنید
3. به آن دسترسی ادمین بدهید — **حذف پیام‌ها** + **مسدود کردن کاربران**
4. تمام. اسپم به‌طور خودکار پاک می‌شود؛ هر وقت خواستید با یک پرسش آن را @ کنید.

همچنین می‌توانید برای گفت‌وگوی هوش مصنوعی مستقیماً به آن پیام خصوصی بدهید.

---

## کاری که انجام می‌دهد

**🚫 ضد اسپم** — تبلیغات، کلاهبرداری‌ها و اسپم رمزارز و قمار را می‌گیرد. از پس کاراکترهای مشابه یونیکد، ترفندهای تمام‌عرض و بی‌عرض، پُرکردن با ایموجی و زبان کوچه‌بازاری برمی‌آید. یک پیش‌فیلتر بی‌هزینه موارد آشکار را پیش از رسیدن به هوش مصنوعی حذف می‌کند، و سیل پیام‌های تکراری بدون هیچ فراخوانی هوش مصنوعی گرفته می‌شود.

**👁️ بینایی** — تصاویر و بندانگشتی ویدیوها را می‌خواند تا تبلیغات تصویری و کلاهبرداری‌های کد QR را بگیرد. در گفت‌وگو، داستان پشت یک عکس را می‌خواند، نه فقط پیکسل‌ها را.

**💬 گفت‌وگو** — در هر گروهی آن را @ کنید یا به‌صورت خصوصی به آن پیام بدهید. چندزبانه است و زبان شما را به‌طور خودکار تشخیص می‌دهد. هر چیزی بپرسید و پاسخی روشن و کاربردی بگیرید — در موضوعات حساس واقع‌بین، با مرزهای معقول در مواردی که واقعاً زیان‌بارند.

---

## میزبانی شخصی

هر ارائه‌دهنده‌ی هوش مصنوعی **سازگار با OpenAI** را بیاورید — [SiliconFlow](https://cloud.siliconflow.cn) (پیش‌فرض)، OpenAI، DeepSeek، یا یک مدل محلی. به دو چیز نیاز دارید:

- **توکن ربات** — [@BotFather](https://t.me/BotFather) ← `/newbot`
- **کلید API هوش مصنوعی** — از ارائه‌دهنده‌تان (پیش‌فرض روی SiliconFlow تنظیم شده است)

### گزینه ۱ — VPS (یک فرمان)

```bash
curl -sL https://raw.githubusercontent.com/ilang-ai/TelegramGuard/main/install.sh | sudo bash
```

کلون می‌کند، وابستگی‌ها را نصب می‌کند، دو کلید شما را می‌پرسد و به‌عنوان یک سرویس systemd اجرا می‌شود. آن را با این دستورها مدیریت کنید:

```bash
systemctl status telegramguard     # status
systemctl restart telegramguard    # restart
journalctl -u telegramguard -f     # live logs
```

### گزینه ۲ — HuggingFace Space (رایگان، بدون سرور)

1. این مخزن را فورک کنید
2. یک [HuggingFace Space](https://huggingface.co/new-space) بسازید ← Docker SDK ← Blank
3. مخزن GitHub ← Settings ← Secrets ← افزودن `HF_TOKEN` (توکن نوشتن HF شما)
4. HF Space ← Settings ← Secrets ← افزودن `BOT_TOKEN` + `AI_API_KEY`
5. HF Space ← Settings ← **ذخیره‌سازی پایدار** را فعال کنید تا `/data` (پایگاه‌داده‌ی SQLite) قابل نوشتن باشد — یا یک راز `DB_PATH` اضافه کنید که به جایی قابل‌نوشتن اشاره کند
6. به GitHub پوش کنید — به‌طور خودکار روی Space مستقر می‌شود

### گزینه ۳ — دستی

```bash
git clone https://github.com/ilang-ai/TelegramGuard.git
cd TelegramGuard
pip install -r requirements.txt
cp .env.example .env         # fill in BOT_TOKEN + AI_API_KEY
set -a; source .env; set +a  # load .env into the environment
python bot.py
```

پس از ساختن ربات‌تان، این‌ها را به [@BotFather](https://t.me/BotFather) بفرستید: `/setjoingroups → Enable` و `/setprivacy → Disable` (تا بتواند پیام‌های گروه را ببیند).

### پیکربندی

همه‌چیز از طریق متغیرهای محیطی تنظیم می‌شود — [`.env.example`](.env.example) را ببینید:

| متغیر | پیش‌فرض | هدف |
|----------|---------|---------|
| `BOT_TOKEN` | *(required)* | توکن ربات تلگرام |
| `AI_API_KEY` | *(required)* | کلید API سازگار با OpenAI |
| `AI_BASE_URL` | `https://api.siliconflow.cn/v1` | نقطه‌ی پایانی ارائه‌دهنده |
| `AI_MODEL` | `deepseek-ai/DeepSeek-V4-Flash` | مدل متنی |
| `AI_VISION_MODELS` | `Qwen/Qwen3-VL-30B…` | زنجیره‌ی جایگزین بینایی (جداشده با کاما) |
| `AI_AUDIO_MODEL` | `Qwen/Qwen3-Omni-30B-A3B-Instruct` | مدل پیام صوتی |
| `AI_IMAGE_MAX_WIDTH` | `600` | کاهش عرض تصویر پیش از فراخوانی‌های بینایی |
| `LEXICON_HARD_THRESHOLD` | `6` | سخت‌گیری پیش‌فیلتر زبان کوچه‌بازاری (بالاتر = سخت‌گیرانه‌تر) |

---

## سفارشی‌سازی هوش مصنوعی

مغز ربات در فایل‌های ساده‌ی `.ilang` جای دارد — [I-Lang Prompt Spec](https://ilang.ai)، جایی که هر `::GENE` یک رفتار را تعریف می‌کند.

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

ژن‌ها را تغییر دهید، ربات را تغییر می‌دهید. برای سفارشی‌سازی: `prompts_demo/` را در `prompts/` کپی کنید (ابتدا بارگذاری می‌شود) و ویرایش کنید.

**[آشنایی با I-Lang Prompt Spec ←](https://ilang.ai)**

---

## معماری

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

ساخته‌شده با **[I-Lang Prompt Spec](https://ilang.ai)** — دستورالعمل‌های ساختارمند هوش مصنوعی همچون کد ژنتیکی.

[![Spec](https://img.shields.io/badge/spec-ilang--ai/ilang--spec-black?logo=github)](https://github.com/ilang-ai/ilang-spec)
[![Web](https://img.shields.io/badge/web-ilang.ai-blue)](https://ilang.ai)
[![HF](https://img.shields.io/badge/HF-i--Lang-yellow?logo=huggingface)](https://huggingface.co/i-Lang)

MIT · © [iLang Inc.](https://eastsoft.com) · [antispam.bot](https://antispam.bot) · [ilang.ai](https://ilang.ai)

</div>
