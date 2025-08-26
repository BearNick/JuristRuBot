from typing import List, Dict
import re
from .citation_normalizer import extract_citations

SUM_RE = re.compile(r"\b\d{1,3}(?:[ \u00A0]\d{3})*(?:[–-]\d{1,3}(?:[ \u00A0]\d{3})*)?\s*₽")
FZ_EDIT_RE = re.compile(r"ФЗ[\--]\d{1,4}[\--]ФЗ\s+от\s+\d{2}\.\d{2}\.\d{4}")

def has_valid_citation(answer_text: str) -> bool:
    cites = extract_citations(answer_text)
    return len(cites) > 0

def has_strict_legal_quality(answer_text: str) -> bool:
    if not has_valid_citation(answer_text):
        return False
    has_amount_or_sanction = bool(SUM_RE.search(answer_text)) or any(
        kw in answer_text.lower()
        for kw in ("лишение права управления", "обязательные работы", "административный арест", "предупреждение")
    )
    if not has_amount_or_sanction:
        return False
    if not FZ_EDIT_RE.search(answer_text):
        return False
    return True