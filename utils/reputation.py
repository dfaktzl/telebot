import re
from database import get_setting
import time

# Cache for dynamic patterns
_CACHE = {
    "pos": None,
    "neg": None,
    "black": None,
    "last_load": 0
}

CACHE_TTL = 300 # 5 minutes

async def _get_patterns():
    """Fetch keywords from DB and compile regex. Cached for 5 minutes."""
    now = time.time()
    if _CACHE["last_load"] > now - CACHE_TTL and _CACHE["pos"]:
        return _CACHE["pos"], _CACHE["neg"], _CACHE["black"]

    pos_raw = await get_setting('positive_keywords', '')
    neg_raw = await get_setting('negative_keywords', '')
    black_raw = await get_setting('blacklist_terms', '')

    pos_list = [re.escape(k.strip()) for k in pos_raw.split(',') if k.strip()]
    neg_list = [re.escape(k.strip()) for k in neg_raw.split(',') if k.strip()]
    black_list = [re.escape(k.strip()) for k in black_raw.split(',') if k.strip()]

    _CACHE["pos"] = re.compile(r'\b(' + '|'.join(sorted(pos_list, key=len, reverse=True)) + r')\b', re.IGNORECASE) if pos_list else None
    _CACHE["neg"] = re.compile(r'\b(' + '|'.join(sorted(neg_list, key=len, reverse=True)) + r')\b', re.IGNORECASE) if neg_list else None
    _CACHE["black"] = re.compile(r'\b(' + '|'.join(black_list) + r')\b', re.IGNORECASE) if black_list else None
    _CACHE["last_load"] = now

    return _CACHE["pos"], _CACHE["neg"], _CACHE["black"]

async def score_sentiment(text: str) -> tuple[int, int]:
    """Returns (positive_count, negative_count) based on dynamic DB keywords."""
    pos_pat, neg_pat, _ = await _get_patterns()
    pos = len(pos_pat.findall(text)) if pos_pat else 0
    neg = len(neg_pat.findall(text)) if neg_pat else 0
    return pos, neg

async def is_illegal_content(text: str) -> bool:
    """Returns True if blacklisted terms from DB are found."""
    _, _, black_pat = await _get_patterns()
    return bool(black_pat.search(text)) if black_pat else False
