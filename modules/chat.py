import json
import logging
import random
import os

from modules import ai_provider
from modules import lexicon
import config

logger = logging.getLogger(__name__)


# Load prompts from .ilang files (prompts/ if exists, else prompts_demo/)
def _load_prompt(name):
    for d in ("prompts", "prompts_demo"):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), d, name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                logger.info("Loaded prompt: " + path + " (" + str(len(content)) + " chars)")
                return content
    logger.warning("Prompt not found: " + name)
    return ""


SYSTEM_PROMPT = _load_prompt("persona.ilang")
ANTISPAM_TEXT_PROMPT = _load_prompt("antispam.ilang")
VISION_PROMPT = _load_prompt("vision.ilang")

if not SYSTEM_PROMPT:
    SYSTEM_PROMPT = "You are TelegramGuard, a helpful AI assistant on Telegram. Reply concisely in the user's language. JSON format: {\"intent\": \"chat\", \"reply\": \"your text\"}"
    logger.warning("Using fallback system prompt")

GROUP_WELCOME = (
    "I-Lang Guard is here\n\n"
    "I auto-clean spam. No config needed.\n"
    "@ me if you need anything.\n\n"
    "Just give me admin permissions (delete messages + ban users)."
)


def _parse(raw):
    if not raw:
        return ("chat", "...")
    t = raw.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1:] if nl > 0 else t[3:]
    if t.endswith("```"):
        t = t[:-3].strip()
    try:
        d = json.loads(t)
        return (d.get("intent", "chat"), d.get("reply", t))
    except json.JSONDecodeError:
        pass
    last_brace = t.rfind("}")
    while last_brace >= 0:
        start = t.rfind("{", 0, last_brace)
        if start >= 0:
            try:
                d = json.loads(t[start:last_brace + 1])
                return (d.get("intent", "chat"), d.get("reply", t))
            except json.JSONDecodeError:
                pass
        last_brace = t.rfind("}", 0, last_brace)
    for line in t.split("\n"):
        line = line.strip()
        if line and not line.startswith("{") and not line.startswith("taint") and not line.startswith("The "):
            return ("chat", line)
    return ("chat", "...")


def _ctx(history, info):
    parts = []
    if info:
        parts.append("[ctx] " + info)
    if history:
        for h in history[-8:]:
            r = "user" if h["role"] == "user" else "bot"
            parts.append(r + ": " + h["text"])
    return "\n".join(parts)


def _deflect():
    lines = [
        "That's a tough one. What else can I help with?",
        "Let's try a different angle. What do you need today?",
        "That's beyond my range. What else is on your mind?",
    ]
    return random.choice(lines)


def _is_spam(raw):
    """Parse a spam-judge reply into True / False / None (couldn't parse it).

    Fixes the old `"spam" in result` substring bug (a wordy 'not spam' counted as
    spam) and the fail-open that replaced it: anything not starting with spam/yes
    silently meant "clean", so a model that prefixes its answer ("Based on the
    above, yes") or gets truncated inside that preamble was a free pass.
    None means unparseable — callers fall back to the lexicon instead of letting
    the message through.
    """
    s = (raw or "").strip().lower().lstrip("\"'`*# 　")
    if not s:
        return None
    if s.startswith(("spam", "yes", "y,", "违规", "是", "有")) or s == "y":
        return True
    if s.startswith(("ok", "no", "n,", "not ", "clean", "正常", "否", "不是", "无")) or s == "n":
        return False
    return None


def _lexicon_fallback(text):
    """Used when the verdict is unparseable or the API call failed: fall back to
    a lexicon hard hit rather than silently letting the message through."""
    try:
        s, _ = lexicon.score(text or "")
        return s >= getattr(config, "LEXICON_HARD_THRESHOLD", 6)
    except Exception as e:
        logger.warning("lexicon fallback failed: " + str(e))
        return False


async def ai_text(text, history=None, context_info=""):
    try:
        c = _ctx(history, context_info)
        prompt = c + "\nuser: " + text if c else "user: " + text
        raw = await ai_provider.generate_text(prompt, system=SYSTEM_PROMPT)
        if not raw:
            return ("chat", _deflect())
        logger.info("AI raw[" + str(len(raw)) + "]: " + raw[:200])
        return _parse(raw)
    except Exception as e:
        logger.warning("AI text exception: " + str(e))
        return ("chat", _deflect())


async def ai_vision(image_bytes, caption="", history=None, context_info=""):
    try:
        c = _ctx(history, context_info)
        prompt = VISION_PROMPT + "\n" + c
        if caption:
            prompt += "\nuser: " + caption
        raw = await ai_provider.generate_vision(prompt, image_bytes, system=SYSTEM_PROMPT)
        return _parse(raw)
    except Exception as e:
        logger.warning("AI vision: " + str(e))
        return ("chat", "Couldn't read that image. Try another one?")


async def ai_voice(audio_bytes, mime_type="audio/ogg", history=None, context_info=""):
    try:
        c = _ctx(history, context_info)
        prompt = c + "\nUser sent a voice message:" if c else "User sent a voice message:"
        fmt = "ogg"
        if "/" in mime_type:
            fmt = mime_type.split("/", 1)[1].split(";")[0] or "ogg"
        raw = await ai_provider.generate_audio(prompt, audio_bytes, fmt=fmt, system=SYSTEM_PROMPT)
        return _parse(raw)
    except Exception as e:
        logger.warning("AI voice: " + str(e))
        return ("chat", "Didn't catch that. Try again or type it out.")


async def ai_judge_group_message(text, sender_context=""):
    try:
        prompt = ANTISPAM_TEXT_PROMPT
        if sender_context:
            prompt += "\n\nSender context: " + sender_context
        prompt += "\n\nMessage content: " + text[:1000]
        # max_tokens 32, not 8: eight tokens is enough to truncate the answer
        # inside a preamble ("Based on the above,"), which leaves nothing to
        # parse and drops the judgement down to the lexicon for no reason.
        raw = await ai_provider.generate_text(prompt, max_tokens=32, temperature=0.0)
        verdict = _is_spam(raw)
        if verdict is None:  # unparseable — don't let it through silently
            logger.warning("spam text verdict unparseable: " + repr((raw or "")[:80]) + " — falling back to lexicon")
            return _lexicon_fallback(text)
        return verdict
    except Exception as e:
        logger.warning("spam text judge failed, falling back to lexicon: " + str(e))
        return _lexicon_fallback(text)


async def ai_judge_group_image(image_bytes, caption="", sender_context=""):
    try:
        prompt = ANTISPAM_TEXT_PROMPT + "\n\nJudge this image. Reply ONLY: spam or ok."
        if sender_context:
            prompt += "\nSender context: " + sender_context
        if caption:
            prompt += "\nCaption: " + caption[:500]
        raw = await ai_provider.generate_vision(prompt, image_bytes, max_tokens=32, temperature=0.0)
        verdict = _is_spam(raw)
        if verdict is None:  # same as above — no silent pass
            logger.warning("spam image verdict unparseable: " + repr((raw or "")[:80]) + " — falling back to lexicon")
            return _lexicon_fallback(caption)
        return verdict
    except Exception as e:
        logger.warning("spam image judge failed, falling back to lexicon: " + str(e))
        return _lexicon_fallback(caption)


async def ai_group_vision(image_bytes, caption="", history=None):
    try:
        ctx = _ctx(history, "GROUP_CHAT: User shared an image and @mentioned you. Comment naturally in 1-2 sentences.")
        prompt = SYSTEM_PROMPT + "\n" + ctx
        if caption:
            prompt += "\nuser: " + caption
        else:
            prompt += "\nuser: [shared an image]"
        raw = await ai_provider.generate_vision(prompt, image_bytes, system=SYSTEM_PROMPT)
        raw = (raw or "").strip()
        if not raw:
            return _deflect()
        intent, reply = _parse(raw)
        if reply in ("...", ""):
            return _deflect()
        return reply
    except Exception:
        return _deflect()


async def ai_group_reply(text, history=None):
    try:
        ctx = _ctx(history, "GROUP_CHAT: You were @mentioned in a group. Reply directly, 1-2 sentences.")
        prompt = ctx + "\nuser: " + text
        raw = await ai_provider.generate_text(prompt, system=SYSTEM_PROMPT)
        raw = (raw or "").strip()
        if not raw:
            return _deflect()
        intent, reply = _parse(raw)
        if reply in ("...", ""):
            return _deflect()
        return reply
    except Exception:
        return _deflect()
