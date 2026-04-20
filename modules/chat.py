import json
import logging
import random
import os
import google.generativeai as genai
import config

logger = logging.getLogger(__name__)

genai.configure(api_key=config.GEMINI_API_KEY)

# Relax Gemini safety filters
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

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
    SYSTEM_PROMPT = "You are TelegramGuard, a helpful AI assistant on Telegram. Reply concisely in the user's language. JSON format: {\"intent\": \"chat\", \"device\": null, \"reply\": \"your text\"}"
    logger.warning("Using fallback system prompt")

GROUP_WELCOME = (
    "I-Lang Guard is here\n\n"
    "I auto-clean spam. No config needed.\n"
    "@ me if you need anything.\n\n"
    "Just give me admin permissions (delete messages + ban users)."
)

model = genai.GenerativeModel(
    config.GEMINI_MODEL,
    system_instruction=SYSTEM_PROMPT,
    safety_settings=SAFETY_SETTINGS
)
vision_model = genai.GenerativeModel(
    config.GEMINI_MODEL,
    safety_settings=SAFETY_SETTINGS
)


def _parse(raw):
    if not raw:
        return ("chat", None, "...")
    t = raw.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1:] if nl > 0 else t[3:]
    if t.endswith("```"):
        t = t[:-3].strip()
    try:
        d = json.loads(t)
        return (d.get("intent", "chat"), d.get("device"), d.get("reply", t))
    except json.JSONDecodeError:
        pass
    last_brace = t.rfind("}")
    while last_brace >= 0:
        start = t.rfind("{", 0, last_brace)
        if start >= 0:
            try:
                d = json.loads(t[start:last_brace + 1])
                return (d.get("intent", "chat"), d.get("device"), d.get("reply", t))
            except json.JSONDecodeError:
                pass
        last_brace = t.rfind("}", 0, last_brace)
    for line in t.split("\n"):
        line = line.strip()
        if line and not line.startswith("{") and not line.startswith("taint") and not line.startswith("The "):
            return ("chat", None, line)
    return ("chat", None, "...")


def _ctx(history, info):
    parts = []
    if info:
        parts.append("[ctx] " + info)
    if history:
        for h in history[-8:]:
            r = "user" if h["role"] == "user" else "bot"
            parts.append(r + ": " + h["text"])
    return "\n".join(parts)


def _safe_text(response):
    """Safely extract text from Gemini response — r.text throws ValueError when blocked."""
    try:
        if response.text:
            return response.text.strip()
    except (ValueError, AttributeError):
        pass
    # Try extracting from candidates
    try:
        if response.candidates:
            for c in response.candidates:
                if hasattr(c, 'content') and c.content and c.content.parts:
                    return c.content.parts[0].text.strip()
    except Exception:
        pass
    return ""


def _deflect():
    lines = [
        "That's a tough one. What else can I help with?",
        "Let's try a different angle. What do you need today?",
        "That's beyond my range. What else is on your mind?",
    ]
    return random.choice(lines)


async def ai_text(text, history=None, context_info=""):
    try:
        c = _ctx(history, context_info)
        prompt = c + "\nuser: " + text if c else "user: " + text
        r = await model.generate_content_async(prompt)
        raw = _safe_text(r)
        if not raw:
            feedback = ""
            if hasattr(r, 'prompt_feedback'):
                feedback = str(r.prompt_feedback)
            if hasattr(r, 'candidates') and r.candidates:
                for cand in r.candidates:
                    if hasattr(cand, 'finish_reason'):
                        feedback += " finish:" + str(cand.finish_reason)
                    if hasattr(cand, 'safety_ratings'):
                        feedback += " safety:" + str(cand.safety_ratings)
            logger.warning("AI empty response. feedback=" + feedback + " prompt_len=" + str(len(prompt)))
            return ("chat", None, _deflect())
        logger.info("AI raw[" + str(len(raw)) + "]: " + raw[:200])
        return _parse(raw)
    except Exception as e:
        logger.warning("AI text exception: " + str(e))
        return ("chat", None, _deflect())


async def ai_vision(image_bytes, caption="", history=None, context_info=""):
    try:
        c = _ctx(history, context_info)
        prompt = VISION_PROMPT + "\n" + c
        if caption:
            prompt += "\nuser: " + caption
        r = await vision_model.generate_content_async([prompt, {"mime_type": "image/jpeg", "data": image_bytes}])
        return _parse(_safe_text(r))
    except Exception as e:
        logger.warning("AI vision: " + str(e))
        return ("chat", None, "Couldn't read that image. Try another one?")


async def ai_voice(audio_bytes, mime_type="audio/ogg", history=None, context_info=""):
    try:
        c = _ctx(history, context_info)
        prompt = SYSTEM_PROMPT + "\n" + c + "\nUser sent a voice message:"
        r = await vision_model.generate_content_async([prompt, {"mime_type": mime_type, "data": audio_bytes}])
        return _parse(_safe_text(r))
    except Exception as e:
        logger.warning("AI voice: " + str(e))
        return ("chat", None, "Didn't catch that. Try again or type it out.")


async def ai_judge_group_message(text):
    try:
        prompt = ANTISPAM_TEXT_PROMPT + "\n\nMessage content: " + text[:1000]
        r = await vision_model.generate_content_async(prompt)
        result = (_safe_text(r) or "ok").lower()
        return "spam" in result
    except Exception:
        return False


async def ai_judge_group_image(image_bytes, caption=""):
    try:
        prompt = ANTISPAM_TEXT_PROMPT + "\n\nJudge this image. Reply ONLY: spam or ok."
        if caption:
            prompt += "\nCaption: " + caption[:500]
        r = await vision_model.generate_content_async([prompt, {"mime_type": "image/jpeg", "data": image_bytes}])
        result = (_safe_text(r) or "ok").lower()
        return "spam" in result
    except Exception:
        return False


async def ai_group_vision(image_bytes, caption="", history=None):
    try:
        ctx = _ctx(history, "GROUP_CHAT: User shared an image and @mentioned you. Comment naturally in 1-2 sentences.")
        prompt = SYSTEM_PROMPT + "\n" + ctx
        if caption:
            prompt += "\nuser: " + caption
        else:
            prompt += "\nuser: [shared an image]"
        r = await vision_model.generate_content_async([prompt, {"mime_type": "image/jpeg", "data": image_bytes}])
        raw = _safe_text(r)
        if not raw:
            return _deflect()
        intent, device, reply = _parse(raw)
        if reply in ("...", ""):
            return _deflect()
        return reply
    except Exception:
        return _deflect()


async def ai_group_reply(text, history=None):
    try:
        ctx = _ctx(history, "GROUP_CHAT: You were @mentioned in a group. Reply directly, 1-2 sentences.")
        prompt = ctx + "\nuser: " + text
        r = await model.generate_content_async(prompt)
        raw = _safe_text(r)
        if not raw:
            return _deflect()
        intent, device, reply = _parse(raw)
        if reply in ("...", ""):
            return _deflect()
        return reply
    except Exception:
        return _deflect()
