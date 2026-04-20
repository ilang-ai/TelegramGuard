"""
Pre-filter: catches obvious spam BEFORE burning an AI API call.
Zero cost. Runs on every message. AI only sees what passes all filters.
"""

import re
import time
import logging

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
    if not msg.forward_date:
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

    # Layer 3: Suspicious new account + link
    if new_account_spam(user, text):
        logger.info("PREFILTER new_account_spam: user=" + str(user.id))
        return "spam"

    # Layer 4: No text, no media = nothing to check
    if not text and not msg.photo and not msg.video:
        return "clean"

    # Layer 5: Rate limiter — can we afford an AI call?
    if not should_use_ai(msg):
        return "clean"  # let it through rather than false-positive

    # Needs AI
    api_limiter.record_call()
    return "ai"
