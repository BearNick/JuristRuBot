import re
from typing import List, Dict

# Простые шаблоны для извлечения ссылок на нормы (статья/часть/пункт)
ART_PAT = re.compile(r'\bст\.?\s*(\d+(\.\d+)*)', re.IGNORECASE)
PART_PAT = re.compile(r'\bч\.?\s*(\d+)', re.IGNORECASE)
POINT_PAT = re.compile(r'\bп\.?\s*(\d+(\.\d+)*)', re.IGNORECASE)

CODES = [
    ("КоАП РФ", re.compile(r'коап\s*рф', re.IGNORECASE)),
    ("УК РФ", re.compile(r'ук\s*рф', re.IGNORECASE)),
    ("ГК РФ", re.compile(r'гк\s*рф', re.IGNORECASE)),
    ("ТК РФ", re.compile(r'тк\s*рф', re.IGNORECASE)),
    ("НК РФ", re.compile(r'нк\s*рф', re.IGNORECASE)),
]

def extract_citations(text: str) -> List[Dict]:
    out: List[Dict] = []
    for code_name, code_rx in CODES:
        if code_rx.search(text):
            # Находим все потенциальные статьи/части/пункты рядом
            for m in ART_PAT.finditer(text):
                item = {"code": code_name, "article": m.group(1), "part": None, "point": None}
                # Пытаемся захватить ближние "ч." и "п."
                # (для MVP — простая стратегия: ищем в фиксированном окне рядом)
                start, end = max(0, m.start()-40), min(len(text), m.end()+40)
                window = text[start:end]
                pm = PART_PAT.search(window)
                qm = POINT_PAT.search(window)
                if pm: item["part"] = pm.group(1)
                if qm: item["point"] = qm.group(1)
                out.append(item)
    # Уникализация
    uniq = []
    seen = set()
    for c in out:
        key = (c["code"], c["article"], c["part"], c["point"])
        if key not in seen:
            seen.add(key); uniq.append(c)
    return uniq
