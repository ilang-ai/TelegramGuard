import json
import logging
import random
import os
import google.generativeai as genai
import config

logger = logging.getLogger(__name__)

genai.configure(api_key=config.GEMINI_API_KEY)

# Load prompts from .ilang files (prompts/ if exists, else prompts_demo/)
def _load_prompt(name):
    for d in ("prompts", "prompts_demo"):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), d, name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return ""

SYSTEM_PROMPT = _load_prompt("persona.ilang")
ANTISPAM_TEXT_PROMPT = _load_prompt("antispam.ilang")
VISION_PROMPT = _load_prompt("vision.ilang")

GROUP_WELCOME = (
    "I-Lang Guard 来了\n\n"
    "垃圾广告我来清理, 全自动, 不用配置\n"
    "有问题可以 @我\n\n"
    "给我管理员权限(删消息+封人)就行, 其他不用管"
)

model = genai.GenerativeModel(config.GEMINI_MODEL, system_instruction=SYSTEM_PROMPT)
vision_model = genai.GenerativeModel(config.GEMINI_MODEL)


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


def _deflect():
    lines = [
        "这个话题不太方便聊, 换一个吧",
        "换个话题? 你今天有什么需要帮忙的?",
        "这个超纲了, 聊点别的吧",
    ]
    return random.choice(lines)


async def ai_text(text, history=None, context_info=""):
    try:
        c = _ctx(history, context_info)
        prompt = c + "\nuser: " + text if c else "user: " + text
        r = await model.generate_content_async(prompt)
        raw = r.text.strip() if r.text else ""
        if not raw:
            return ("chat", None, _deflect())
        return _parse(raw)
    except Exception as e:
        logger.warning("AI text: " + str(e))
        return ("chat", None, _deflect())


async def ai_vision(image_bytes, caption="", history=None, context_info=""):
    try:
        c = _ctx(history, context_info)
        prompt = VISION_PROMPT + "\n" + c
        if caption:
            prompt += "\nuser: " + caption
        r = await vision_model.generate_content_async([prompt, {"mime_type": "image/jpeg", "data": image_bytes}])
        return _parse(r.text if r.text else "")
    except Exception as e:
        logger.warning("AI vision: " + str(e))
        return ("chat", None, "图片没看清, 再发一张?")


async def ai_voice(audio_bytes, mime_type="audio/ogg", history=None, context_info=""):
    try:
        c = _ctx(history, context_info)
        prompt = SYSTEM_PROMPT + "\n" + c + "\nUser sent a voice message:"
        r = await vision_model.generate_content_async([prompt, {"mime_type": mime_type, "data": audio_bytes}])
        return _parse(r.text if r.text else "")
    except Exception as e:
        logger.warning("AI voice: " + str(e))
        return ("chat", None, "语音没听清, 再说一次或者打字都行")


async def ai_judge_group_message(text):
    try:
        prompt = ANTISPAM_TEXT_PROMPT + "\n\n消息内容: " + text[:1000]
        r = await vision_model.generate_content_async(prompt)
        result = r.text.strip().lower() if r.text else "ok"
        return "spam" in result
    except Exception:
        return False


async def ai_judge_group_image(image_bytes, caption=""):
    try:
        prompt = ANTISPAM_TEXT_PROMPT + "\n\n判断这张图片是否是spam。只回复 spam 或 ok。"
        if caption:
            prompt += "\nCaption: " + caption[:500]
        r = await vision_model.generate_content_async([prompt, {"mime_type": "image/jpeg", "data": image_bytes}])
        result = r.text.strip().lower() if r.text else "ok"
        return "spam" in result
    except Exception:
        return False


async def ai_group_vision(image_bytes, caption="", history=None):
    try:
        ctx = _ctx(history, "GROUP_CHAT: 用户在群里发了张图片@你, 简短评论1-2句话")
        prompt = SYSTEM_PROMPT + "\n" + ctx
        if caption:
            prompt += "\nuser: " + caption
        else:
            prompt += "\nuser: [发了张图片]"
        r = await vision_model.generate_content_async([prompt, {"mime_type": "image/jpeg", "data": image_bytes}])
        raw = r.text.strip() if r.text else ""
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
        ctx = _ctx(history, "GROUP_CHAT: 你在群里被@了, 直接回答, 简短2句话")
        prompt = ctx + "\nuser: " + text
        r = await model.generate_content_async(prompt)
        raw = r.text.strip() if r.text else ""
        if not raw:
            return _deflect()
        intent, device, reply = _parse(raw)
        if reply in ("...", ""):
            return _deflect()
        return reply
    except Exception:
        return _deflect()
