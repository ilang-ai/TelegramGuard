<div align="center">

# 🛡️ antispam.bot

**الحارس الذكي الذي يُبقي مجموعات تيليجرام نظيفة — ويجيب فعلاً عن أسئلتك.**

مفتوح المصدر (MIT)، بلا إعداد، وقابل للاستضافة الذاتية — مشروع **TelegramGuard**.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Powered by I-Lang](https://img.shields.io/badge/powered%20by-I--Lang%20Spec-blueviolet)](https://ilang.ai)
[![AI: OpenAI-compatible](https://img.shields.io/badge/AI-OpenAI--compatible-06D6A0)](#self-host)

🌐 [English](README.md) · [中文](README_CN.md) · [Русский](README_RU.md) · [Español](README_ES.md) · [العربية](README_AR.md) · [فارسی](README_FA.md)

</div>

---

## أضِفه إلى مجموعتك (بلا إعداد)

أضِف البوت الرسمي — بلا تثبيت، بلا إعداد، بلا تكلفة.

### ← [@iLangGuardBot](https://t.me/iLangGuardBot)

1. ابحث عن `@iLangGuardBot` في تيليجرام
2. أضِفه إلى مجموعتك
3. امنحه صلاحية المشرف — **حذف الرسائل** + **حظر المستخدمين**
4. انتهى. يُنظَّف السبام تلقائياً؛ وأشِر إليه بعلامة @ في أي وقت بسؤالك.

يمكنك أيضاً مراسلته مباشرةً على الخاص للدردشة بالذكاء الاصطناعي.

---

## ماذا يفعل

**🚫 مكافحة السبام** — يلتقط الإعلانات وعمليات الاحتيال وسبام العملات المشفّرة والمقامرة. يكشف حِيَل محارف يونيكود المتشابهة، والمسافات كاملة العرض وعديمة العرض، وحشو الرموز التعبيرية والعامية. ومرشّح أوّلي بلا تكلفة يقضي على الواضح منها قبل أن يصل إلى الذكاء الاصطناعي، ويُلتقَط التكرار المُغرِق دون أي استدعاء للذكاء الاصطناعي إطلاقاً.

**👁️ الرؤية** — يقرأ الصور ومصغّرات الفيديو ليلتقط الإعلانات المصوّرة وعمليات الاحتيال عبر رموز QR. وفي المحادثة، يقرأ القصة الكامنة خلف الصورة، لا مجرد وحدات البكسل.

**💬 المحادثة** — أشِر إليه بعلامة @ في أي مجموعة أو راسِله على الخاص. متعدّد اللغات، ويكتشف لغتك تلقائياً. اسأله أي شيء واحصل على إجابة واضحة ومفيدة — دقيقة في المواضيع الحسّاسة، مع حدود منطقية تجاه ما هو ضارّ حقاً.

---

## الاستضافة الذاتية

استخدم أي مزوّد ذكاء اصطناعي **متوافق مع OpenAI** — [SiliconFlow](https://cloud.siliconflow.cn) (الافتراضي) أو OpenAI أو DeepSeek أو نموذجاً محلياً. تحتاج إلى أمرَين:

- **رمز البوت (Bot Token)** — [@BotFather](https://t.me/BotFather) → `/newbot`
- **مفتاح واجهة الذكاء الاصطناعي (AI API Key)** — من مزوّدك (الإعداد الافتراضي يستهدف SiliconFlow)

### الخيار 1 — VPS (أمر واحد)

```bash
curl -sL https://raw.githubusercontent.com/ilang-ai/TelegramGuard/main/install.sh | sudo bash
```

يستنسخ المشروع، ويثبّت التبعيات، ويطلب مفتاحَيك، ثم يعمل كخدمة systemd. أدِرْه عبر:

```bash
systemctl status telegramguard     # status
systemctl restart telegramguard    # restart
journalctl -u telegramguard -f     # live logs
```

### الخيار 2 — HuggingFace Space (مجاني، بلا خادم)

1. فرّع هذا المستودع
2. أنشئ [HuggingFace Space](https://huggingface.co/new-space) → Docker SDK → Blank
3. مستودع GitHub → Settings → Secrets → أضِف `HF_TOKEN` (رمز الكتابة الخاص بك على HuggingFace)
4. HF Space → Settings → Secrets → أضِف `BOT_TOKEN` + `AI_API_KEY`
5. HF Space → Settings → فعِّل **التخزين الدائم** حتى يصبح `/data` (قاعدة بيانات SQLite) قابلاً للكتابة — أو أضِف سرّاً باسم `DB_PATH` يشير إلى موقع قابل للكتابة
6. ادفع إلى GitHub — فيُنشَر تلقائياً إلى الـ Space

### الخيار 3 — يدوي

```bash
git clone https://github.com/ilang-ai/TelegramGuard.git
cd TelegramGuard
pip install -r requirements.txt
cp .env.example .env         # fill in BOT_TOKEN + AI_API_KEY
set -a; source .env; set +a  # load .env into the environment
python bot.py
```

بعد إنشاء البوت، أرسِل إلى [@BotFather](https://t.me/BotFather): `/setjoingroups → Enable` و`/setprivacy → Disable` (حتى يتمكّن من رؤية رسائل المجموعة).

### الإعدادات

يُضبَط كل شيء عبر متغيّرات البيئة — راجِع [`.env.example`](.env.example):

| المتغيّر | القيمة الافتراضية | الغرض |
|----------|---------|---------|
| `BOT_TOKEN` | *(required)* | رمز بوت تيليجرام |
| `AI_API_KEY` | *(required)* | مفتاح واجهة برمجة متوافق مع OpenAI |
| `AI_BASE_URL` | `https://api.siliconflow.cn/v1` | نقطة نهاية المزوّد |
| `AI_MODEL` | `deepseek-ai/DeepSeek-V4-Flash` | نموذج النصوص |
| `AI_VISION_MODELS` | `Qwen/Qwen3-VL-30B…` | سلسلة احتياطية لنماذج الرؤية (مفصولة بفواصل) |
| `AI_AUDIO_MODEL` | `Qwen/Qwen3-Omni-30B-A3B-Instruct` | نموذج الرسائل الصوتية |
| `AI_IMAGE_MAX_WIDTH` | `600` | عرض التصغير قبل استدعاءات الرؤية |
| `LEXICON_HARD_THRESHOLD` | `6` | صرامة المرشّح الأوّلي للعامية (الأعلى = أكثر صرامة) |

---

## تخصيص الذكاء الاصطناعي

يقبع عقل البوت في ملفات `.ilang` بسيطة — [I-Lang Prompt Spec](https://ilang.ai)، حيث يُعرّف كل `::GENE` سلوكاً.

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

غيِّر الجينات، يتغيّر البوت. للتخصيص: انسخ `prompts_demo/` إلى `prompts/` (تُحمَّل أولاً) وحرِّرها.

**[تعرّف على I-Lang Prompt Spec ←](https://ilang.ai)**

---

## البنية

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

مبنيّ باستخدام **[I-Lang Prompt Spec](https://ilang.ai)** — تعليمات ذكاء اصطناعي مُنظَّمة كشيفرة جينية.

[![Spec](https://img.shields.io/badge/spec-ilang--ai/ilang--spec-black?logo=github)](https://github.com/ilang-ai/ilang-spec)
[![Web](https://img.shields.io/badge/web-ilang.ai-blue)](https://ilang.ai)
[![HF](https://img.shields.io/badge/HF-i--Lang-yellow?logo=huggingface)](https://huggingface.co/i-Lang)

MIT · © [iLang Inc.](https://eastsoft.com) · [antispam.bot](https://antispam.bot) · [ilang.ai](https://ilang.ai)

</div>
