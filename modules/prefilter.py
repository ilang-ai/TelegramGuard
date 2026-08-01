"""
Pre-filter: catches obvious spam BEFORE burning an AI API call.
Zero cost. Runs on every message. AI only sees what passes all filters.
"""

import re
import time
import logging

from modules import lexicon

logger = logging.getLogger(__name__)

# Spam keyword patterns (multilingual)
SPAM_KEYWORDS = re.compile(
    r'加[我微v]|私聊领|免费领|日[赚入]|月入[过百千万]|'
    r'代[开做理]|招[代聘]|兼\s*职|刷\s*单|'
    r'翻[几十百]倍|稳赚|保本|零风险|'
    r'[\U0001F4B0\U0001F4B8\U0001F911]{2,}|'  # money emoji spam
    r'click here|earn money|work from home|make \$|'
    r'free crypto|airdrop|whitelist spot|'
    r'join (?:my|our|this) (?:channel|group)|'
    r't\.me/(?:joinchat|[+])',
    re.IGNORECASE
)

# URL patterns
URL_PATTERN = re.compile(
    r'https?://|t\.me/|bit\.ly|tinyurl|wa\.me|'
    r'@\w+bot\b',
    re.IGNORECASE
)

# Contact info patterns
CONTACT_PATTERN = re.compile(
    r'[\U0001F4DE\U0001F4F1]|'  # phone emojis
    r'(?:whatsapp|telegram|wechat|微信|qq)\s*[:：]?\s*\d|'
    r'(?:加|add)\s*(?:我|me)',
    re.IGNORECASE
)


class APIRateLimiter:
    """Token bucket rate limiter for AI API calls."""

    def __init__(self, max_calls=50, window=60):
        self.max_calls = max_calls  # max calls per window
        self.window = window        # window in seconds
        self.calls = []             # timestamps of recent calls

    def can_call(self):
        """Check if we can make another API call."""
        now = time.time()
        self.calls = [t for t in self.calls if now - t < self.window]
        return len(self.calls) < self.max_calls

    def record_call(self):
        """Record an API call."""
        self.calls.append(time.time())

    def remaining(self):
        """How many calls left in current window."""
        now = time.time()
        self.calls = [t for t in self.calls if now - t < self.window]
        return max(0, self.max_calls - len(self.calls))

    def is_critical(self):
        """Below 20% budget — switch to sampling mode."""
        return self.remaining() < self.max_calls * 0.2


# Global rate limiter: 50 AI calls per minute (adjustable)
api_limiter = APIRateLimiter(max_calls=50, window=60)


def keyword_spam(text):
    """Fast keyword check. Returns True if obvious spam."""
    if not text:
        return False
    # Keyword match + has URL or contact = almost certainly spam
    has_keywords = bool(SPAM_KEYWORDS.search(text))
    has_url = bool(URL_PATTERN.search(text))
    has_contact = bool(CONTACT_PATTERN.search(text))

    if has_keywords and (has_url or has_contact):
        return True

    # Pure contact harvesting: just a contact method, no real conversation
    if has_contact and len(text) < 100 and not any(c in text for c in '?？'):
        return True

    return False


def forward_spam(msg):
    """Forwarded message with link/contact = spam."""
    # forward_origin, not forward_date: Bot API 7.0 replaced the flat forward_*
    # fields and PTB dropped the attribute entirely, so reading msg.forward_date
    # raises AttributeError — which crashed this filter on every message.
    if not getattr(msg, "forward_origin", None):
        return False
    text = msg.text or msg.caption or ""
    if URL_PATTERN.search(text) or CONTACT_PATTERN.search(text):
        return True
    # Forwarded media with no caption from non-group member = suspicious
    if not text and (msg.photo or msg.video or msg.document):
        return True
    return False


def new_account_spam(user, text):
    """New/suspicious accounts with links = spam."""
    if not text or not URL_PATTERN.search(text):
        return False
    # No username + no profile photo + has link = high spam probability
    suspicious = 0
    if not user.username:
        suspicious += 1
    if not user.first_name or len(user.first_name) < 2:
        suspicious += 1
    # Name is just emojis or special chars
    if user.first_name and not any(c.isalpha() for c in user.first_name):
        suspicious += 1
    return suspicious >= 2


def has_judgeable_media(msg):
    """True when the message carries something a judge can actually look at.

    Used to decide whether a caption-less message is worth an AI call. It is not
    just photo/video: a sticker, a GIF, a round video and a document all have a
    thumbnail the vision judge can read, and a poll, a shared contact, a venue or
    an audio file all carry sender-controlled text (question and options, name
    and phone number, file name, track title) that the text judge can read.

    Voice notes, locations and dice are deliberately absent — there is no text
    and no image on them, so an AI call would be judging the sender's display
    name and nothing else.
    """
    return bool(
        msg.photo or msg.video or msg.document or msg.sticker or
        msg.animation or msg.video_note or msg.audio or
        msg.poll or msg.contact or msg.venue or
        getattr(msg, "game", None) or getattr(msg, "invoice", None)
    )


def should_use_ai(msg):
    """Decide if this message needs AI analysis or if we should skip/sample."""
    if not api_limiter.can_call():
        logger.warning("API rate limit hit — falling back to rules only")
        return False

    if api_limiter.is_critical():
        # Sampling mode: only check 1 in 3 messages
        import random
        if random.random() > 0.33:
            logger.info("API budget critical — sampling mode, skipping this message")
            return False

    return True


def prefilter(msg, user, text):
    """
    Run all pre-filters. Returns:
      "spam"  — definitely spam, skip AI, nuke immediately
      "clean" — definitely clean, skip AI
      "ai"    — unclear, needs AI analysis
    """
    # Layer 1: Forward spam (zero false positive)
    if forward_spam(msg):
        logger.info("PREFILTER forward_spam: user=" + str(user.id))
        return "spam"

    # Layer 2: Keyword + link/contact (very high accuracy)
    if text and keyword_spam(text):
        logger.info("PREFILTER keyword_spam: user=" + str(user.id) + " text=" + text[:50])
        return "spam"

    # Layer 2.5: Chinese slang lexicon — normalized scoring (NFKC + zero-width +
    # homoglyph), catches full-width / lookalike / split-char evasion the regex misses
    # (disguised 收米 / 加V / 日结 / 上车 ...).
    if text and lexicon.is_hard_spam(text):
        logger.info("PREFILTER lexicon_spam: user=" + str(user.id) + " text=" + text[:50])
        return "spam"

    # Layer 3: Suspicious new account + link
    if new_account_spam(user, text):
        logger.info("PREFILTER new_account_spam: user=" + str(user.id))
        return "spam"

    # Layer 4: nothing to check at all.
    # Tested against msg, not the text argument: the caller passes a judge string
    # that also carries hidden text (link targets, forward origin, display name),
    # so it is practically never empty and this layer would never fire. It also
    # used to list only photo/video, which meant every caption-less sticker,
    # document, GIF or poll was declared clean here and the judging branches for
    # them downstream could never run.
    if not (msg.text or msg.caption) and not has_judgeable_media(msg):
        return "clean"

    # Layer 5: Rate limiter — can we afford an AI call?
    if not should_use_ai(msg):
        return "clean"  # let it through rather than false-positive

    # Needs AI
    api_limiter.record_call()
    return "ai"
