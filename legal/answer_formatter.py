from typing import List, Dict
from core.config import USER_DISCLAIMER

def format_answer(model_text: str, used_sources: List[Dict]) -> str:
    # В конец добавим источники и дисклеймер
    src_lines = []
    for s in used_sources[:6]:
        src_lines.append(f"- {s.get('title') or s.get('url')} — {s.get('url')}")
    src_block = "\n".join(src_lines) if src_lines else "- (источники не найдены)"
    return f"{model_text}\n\nИсточники:\n{src_block}\n\n{USER_DISCLAIMER}"
