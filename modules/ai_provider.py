"""
AI provider layer — OpenAI-compatible.

TelegramGuard talks to any OpenAI-compatible chat API: SiliconFlow (default),
OpenAI, DeepSeek, a local vLLM/Ollama, or any relay. Business code never imports
a vendor SDK — it calls generate_text / generate_vision / generate_audio here.

Config (all via env, see config.py):
  AI_API_KEY        — your key
  AI_BASE_URL       — endpoint (default https://api.siliconflow.cn/v1)
  AI_MODEL          — text model
  AI_VISION_MODELS  — comma-separated vision fallback chain (first fails -> next)
  AI_AUDIO_MODEL    — audio-capable model (optional; voice degrades gracefully)
  AI_IMAGE_MAX_WIDTH — downscale images before upload (default 600)

Optional second provider, used only when the primary is unreachable:
  AI_FALLBACK_API_KEY  — set this to enable the fallback at all
  AI_FALLBACK_BASE_URL — endpoint of the backup relay/vendor
  AI_FALLBACK_MODEL    — text/judge model there
  AI_FALLBACK_VISION_MODEL — vision model there (optional; text model is
                             reused when this is unset)
Leave AI_FALLBACK_API_KEY empty and behaviour is exactly as before.

Design: lazy client init (no network at import, no crash on missing key),
images downscaled before upload, vision falls back down the model chain.
"""

import base64
import io
import logging

import config

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

try:
    from PIL import Image
except ImportError:
    Image = None


class AIError(Exception):
    pass


_clients = {}

PRIMARY = "primary"
FALLBACK = "fallback"


def _get_client(which=PRIMARY):
    if AsyncOpenAI is None:
        raise AIError("openai package not installed (pip install openai)")
    if which not in _clients:
        if which == FALLBACK:
            key = getattr(config, "AI_FALLBACK_API_KEY", "")
            base = getattr(config, "AI_FALLBACK_BASE_URL", "")
            if not key or not base:
                raise AIError("fallback provider not configured")
        else:
            key = getattr(config, "AI_API_KEY", "")
            base = getattr(config, "AI_BASE_URL", "https://api.siliconflow.cn/v1")
            if not key:
                raise AIError("AI_API_KEY not set")
        _clients[which] = AsyncOpenAI(api_key=key, base_url=base, timeout=90)
    return _clients[which]


def _fallback_enabled():
    return bool(getattr(config, "AI_FALLBACK_API_KEY", "")
                and getattr(config, "AI_FALLBACK_BASE_URL", ""))


def _with_fallback(models, vision=False):
    """Append the backup provider to a model chain, if one is configured.

    Entries are either "model" (primary provider) or (FALLBACK, "model").
    Without AI_FALLBACK_API_KEY this returns the chain untouched, so the
    default deployment behaves exactly as it did before.
    """
    if isinstance(models, str):
        models = [models]
    chain = list(models)
    if _fallback_enabled():
        m = ""
        if vision:
            m = getattr(config, "AI_FALLBACK_VISION_MODEL", "")
        if not m:
            m = getattr(config, "AI_FALLBACK_MODEL", "")
        if m:
            chain.append((FALLBACK, m))
    return chain


def _text_model():
    return getattr(config, "AI_MODEL", "deepseek-ai/DeepSeek-V4-Flash")


def _vision_models():
    raw = getattr(config, "AI_VISION_MODELS", "")
    if raw:
        return [m.strip() for m in raw.split(",") if m.strip()]
    return [
        "Qwen/Qwen3-VL-30B-A3B-Instruct",
        "Qwen/Qwen3-VL-32B-Instruct",
        "Qwen/Qwen3-VL-8B-Instruct",
    ]


def _audio_model():
    return getattr(config, "AI_AUDIO_MODEL", "Qwen/Qwen3-Omni-30B-A3B-Instruct")


def _compress(image_bytes):
    max_w = getattr(config, "AI_IMAGE_MAX_WIDTH", 600)
    if Image is None or not max_w:
        return image_bytes
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if img.width > max_w:
            h = max(1, int(img.height * max_w / img.width))
            img = img.resize((max_w, h))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except Exception as e:
        logger.warning("image compress failed, using original: " + str(e))
        return image_bytes


def _image_part(image_bytes):
    b64 = base64.b64encode(_compress(image_bytes)).decode()
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}


async def _chat(models, messages, max_tokens, temperature):
    if isinstance(models, str):
        models = [models]
    last_err = None
    for entry in models:
        # entry is "model" (primary provider) or (FALLBACK, "model")
        try:
            if isinstance(entry, (tuple, list)):
                which, m = entry[0], entry[1]
            else:
                which, m = PRIMARY, entry
            client = _get_client(which)
        except Exception as e:
            last_err = e
            logger.warning("[AI] entry %r unusable: %s, skipping", entry, e)
            continue
        try:
            resp = await client.chat.completions.create(
                model=m, messages=messages, max_tokens=max_tokens, temperature=temperature
            )
            txt = (resp.choices[0].message.content or "").strip()
            if txt:
                return txt
            last_err = AIError("empty response")
        except Exception as e:
            last_err = e
            logger.warning("[AI] provider=%s model=%s failed: %s", which, m, e)
    raise AIError("all models failed: " + str(last_err))


async def generate_text(prompt, system=None, max_tokens=800, temperature=0.7):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return await _chat(_with_fallback(_text_model()), msgs, max_tokens, temperature)


async def generate_vision(prompt, image_bytes, system=None, max_tokens=800, temperature=0.4):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": [
        {"type": "text", "text": prompt},
        _image_part(image_bytes),
    ]})
    return await _chat(_with_fallback(_vision_models(), vision=True), msgs, max_tokens, temperature)


async def generate_audio(prompt, audio_bytes, fmt="ogg", system=None, max_tokens=800, temperature=0.7):
    b64 = base64.b64encode(audio_bytes).decode()
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "input_audio", "input_audio": {"data": b64, "format": fmt}},
    ]})
    return await _chat(_audio_model(), msgs, max_tokens, temperature)
