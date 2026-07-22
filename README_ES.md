<div align="center">

# 🛡️ antispam.bot

**El guardián con IA que mantiene limpios tus grupos de Telegram — y de verdad responde a tus preguntas.**

Código abierto (MIT), sin configuración, autoalojable — el proyecto **TelegramGuard**.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Powered by I-Lang](https://img.shields.io/badge/powered%20by-I--Lang%20Spec-blueviolet)](https://ilang.ai)
[![AI: OpenAI-compatible](https://img.shields.io/badge/AI-OpenAI--compatible-06D6A0)](#self-host)

🌐 [English](README.md) · [中文](README_CN.md) · [Русский](README_RU.md) · [Español](README_ES.md) · [العربية](README_AR.md) · [فارسی](README_FA.md)

</div>

---

## Añádelo a tu grupo (sin configuración)

Añade el bot oficial — sin instalación, sin configuración, sin coste.

### → [@iLangGuardBot](https://t.me/iLangGuardBot)

1. Busca `@iLangGuardBot` en Telegram
2. Añádelo a tu grupo
3. Dale permisos de administrador — **eliminar mensajes** + **expulsar usuarios**
4. Listo. El spam se elimina automáticamente; menciónalo con @ en cualquier momento para hacerle una pregunta.

También puedes escribirle por mensaje directo para chatear con la IA.

---

## Qué hace

**🚫 Antispam** — Detecta anuncios, estafas y spam de criptomonedas y apuestas. Ve a través de los caracteres Unicode parecidos, los trucos de ancho completo y ancho cero, el relleno de emojis y la jerga. Un prefiltro de coste cero elimina lo evidente antes de que llegue a la IA, y el flujo repetido se detecta sin ninguna llamada a la IA.

**👁️ Visión** — Lee imágenes y miniaturas de vídeo para detectar anuncios basados en imágenes y estafas con códigos QR. En el chat, interpreta la historia detrás de una foto, no solo los píxeles.

**💬 Chat** — Menciónalo con @ en cualquier grupo o escríbele en privado. Multilingüe, detecta automáticamente tu idioma. Pregúntale lo que quieras y obtén una respuesta clara y útil — objetiva en temas delicados, con límites sensatos en los realmente dañinos.

---

## Autoalojamiento

Usa cualquier proveedor de IA **compatible con OpenAI** — [SiliconFlow](https://cloud.siliconflow.cn) (predeterminado), OpenAI, DeepSeek o un modelo local. Necesitas dos cosas:

- **Token del bot** — [@BotFather](https://t.me/BotFather) → `/newbot`
- **Clave de API de IA** — de tu proveedor (por defecto apunta a SiliconFlow)

### Opción 1 — VPS (un comando)

```bash
curl -sL https://raw.githubusercontent.com/ilang-ai/TelegramGuard/main/install.sh | sudo bash
```

Clona el repositorio, instala las dependencias, te pide tus dos claves y se ejecuta como servicio systemd. Gestiónalo con:

```bash
systemctl status telegramguard     # status
systemctl restart telegramguard    # restart
journalctl -u telegramguard -f     # live logs
```

### Opción 2 — HuggingFace Space (gratis, sin servidor)

1. Haz un fork de este repositorio
2. Crea un [HuggingFace Space](https://huggingface.co/new-space) → Docker SDK → Blank
3. Repositorio de GitHub → Settings → Secrets → añade `HF_TOKEN` (tu token de escritura de HF)
4. HF Space → Settings → Secrets → añade `BOT_TOKEN` + `AI_API_KEY`
5. HF Space → Settings → activa el **almacenamiento persistente** para que `/data` (la base de datos SQLite) sea escribible — o añade un secreto `DB_PATH` que apunte a una ubicación escribible
6. Haz push a GitHub — se despliega automáticamente en el Space

### Opción 3 — Manual

```bash
git clone https://github.com/ilang-ai/TelegramGuard.git
cd TelegramGuard
pip install -r requirements.txt
cp .env.example .env         # fill in BOT_TOKEN + AI_API_KEY
set -a; source .env; set +a  # load .env into the environment
python bot.py
```

Después de crear tu bot, envía a [@BotFather](https://t.me/BotFather): `/setjoingroups → Enable` y `/setprivacy → Disable` (para que pueda ver los mensajes del grupo).

### Configuración

Todo se configura mediante variables de entorno — consulta [`.env.example`](.env.example):

| Variable | Default | Propósito |
|----------|---------|---------|
| `BOT_TOKEN` | *(required)* | Token del bot de Telegram |
| `AI_API_KEY` | *(required)* | Clave de API compatible con OpenAI |
| `AI_BASE_URL` | `https://api.siliconflow.cn/v1` | Endpoint del proveedor |
| `AI_MODEL` | `deepseek-ai/DeepSeek-V4-Flash` | Modelo de texto |
| `AI_VISION_MODELS` | `Qwen/Qwen3-VL-30B…` | Cadena de respaldo de visión (separada por comas) |
| `AI_AUDIO_MODEL` | `Qwen/Qwen3-Omni-30B-A3B-Instruct` | Modelo para mensajes de voz |
| `AI_IMAGE_MAX_WIDTH` | `600` | Ancho de reducción antes de las llamadas de visión |
| `LEXICON_HARD_THRESHOLD` | `6` | Rigor del prefiltro de jerga (mayor = más estricto) |

---

## Personaliza la IA

El cerebro del bot vive en simples archivos `.ilang` — [I-Lang Prompt Spec](https://ilang.ai), donde cada `::GENE` define un comportamiento.

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

Cambia los genes, cambia el bot. Para personalizar: copia `prompts_demo/` a `prompts/` (se carga primero) y edítalo.

**[Aprende la I-Lang Prompt Spec →](https://ilang.ai)**

---

## Arquitectura

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

Construido con **[I-Lang Prompt Spec](https://ilang.ai)** — instrucciones de IA estructuradas como código genético.

[![Spec](https://img.shields.io/badge/spec-ilang--ai/ilang--spec-black?logo=github)](https://github.com/ilang-ai/ilang-spec)
[![Web](https://img.shields.io/badge/web-ilang.ai-blue)](https://ilang.ai)
[![HF](https://img.shields.io/badge/HF-i--Lang-yellow?logo=huggingface)](https://huggingface.co/i-Lang)

MIT · © [iLang Inc.](https://eastsoft.com) · [antispam.bot](https://antispam.bot) · [ilang.ai](https://ilang.ai)

</div>
