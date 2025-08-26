from core.config import MAX_USER_CHARS

def clamp_text(s: str) -> str:
    s = s.strip()
    if len(s) > MAX_USER_CHARS:
        return s[:MAX_USER_CHARS]
    return s
