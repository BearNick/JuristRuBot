# coding: utf-8
"""
Строгая фильтрация и ранжирование источников по целевым нормам (QUAL).
QUAL формат: ["КоАП РФ;20.1;1;мелкое хулиганство", "УК РФ;119;1;угроза убийством", ...]
"""

from __future__ import annotations
import re
from typing import List, Dict, Tuple

# извлекаем кодекс / статью / часть из текста или URL
RE_ART = re.compile(r"(?:ст\.?|стать[ьяи])\s*([0-9]+(?:\.[0-9]+)?)\b", re.IGNORECASE)
RE_PART = re.compile(r"(?:ч\.?|част[ьи])\s*([0-9]+)\b", re.IGNORECASE)
RE_ART_NUM = re.compile(r"\b([0-9]+(?:\.[0-9]+)?)\b")
RE_CODE = re.compile(
    r"\b(коап\s*рф|уголовн\w*\s*кодекс|ук\s*рф|гражданск\w*\s*кодекс|гк\s*рф|упк\s*рф|кпк\s*рф)\b",
    re.IGNORECASE,
)

def _norm_code(s: str) -> str:
    s = s.lower()
    if "коап" in s: return "коап рф"
    if "уголов" in s or re.search(r"\buk\b", s): return "ук рф"
    if "гражданск" in s or re.search(r"\bgк\b", s): return "гк рф"
    if "упк" in s or "кпк" in s: return "упк рф"
    return s.strip()

def _parse_norms_from_text(s: str) -> Tuple[str, str, str]:
    """Возвращает (code, article, part) — любое может быть пустым."""
    code = ""
    mcode = RE_CODE.search(s or "")
    if mcode:
        code = _norm_code(mcode.group(1))
    art = ""
    mart = RE_ART.search(s or "")
    if mart:
        art = mart.group(1)
    part = ""
    mpart = RE_PART.search(s or "")
    if mpart:
        part = mpart.group(1)
    return code, art, part

def _targets_from_qual(qual: List[str]) -> List[Tuple[str, str, str]]:
    """QUAL -> [(code, article, part)]"""
    targets: List[Tuple[str, str, str]] = []
    for rec in qual or []:
        parts = [p.strip() for p in rec.split(";")]
        if len(parts) >= 2:
            code = _norm_code(parts[0])
            art = parts[1]
            part = parts[2] if len(parts) >= 3 else ""
            targets.append((code, art, part))
    return targets

def _mentions_unrelated_article(text: str, target_articles: set[str]) -> bool:
    """
    Если в тексте встречается номер статьи, и он НЕ из target_articles — считаем нерелевантным.
    (защита от «УК 120» и т.п.)
    """
    # Сначала ищем явные «ст. N»
    arts = set(m.group(1) for m in RE_ART.finditer(text))
    if arts and not (arts & target_articles):
        return True
    # Если явных «ст.» нет, но есть одиночные номера и среди них есть НЕ таргетные — не отсекаем,
    # т.к. это может быть год/номер ФЗ; строгий отсев делаем только по «ст. N».
    return False

def _score_item(item: Dict, targets: List[Tuple[str, str, str]]) -> int:
    """
    Считаем очки:
      +4 совпала статья
      +2 совпал кодекс
      +1 совпала часть
    """
    txt = " ".join([
        item.get("title") or "",
        item.get("snippet") or "",
        item.get("url") or "",
        item.get("source") or "",
    ])
    code, art, part = _parse_norms_from_text(txt)

    score = 0
    for (t_code, t_art, t_part) in targets:
        if t_art and art and (t_art == art):
            score += 4
        if t_code and code and (t_code == code):
            score += 2
        if t_part and part and (t_part == part):
            score += 1
    return score

def filter_and_rank_pages(
    pages: List[Dict],
    qual: List[str],
    min_keep: int = 2,
    max_keep: int = 6,
    strict: bool = True,
) -> List[Dict]:
    """
    Строго оставляем страницы, где явно фигурирует ТА ЖЕ статья, что в QUAL.
    Дополнительно плюсуем за совпадение кодекса/части.
    Если после строгой фильтрации пусто — оставляем min_keep лучших по мягкому скору (без строгого отсева),
    чтобы не сломать ответ.
    """
    if not pages:
        return []
    targets = _targets_from_qual(qual)
    if not targets:
        return pages[:max_keep]

    target_articles = {t[1] for t in targets if t[1]}

    # 1) STRONG FILTER: статья должна совпасть, и не должно быть «сторонних» статей в явном виде
    strong: List[Tuple[int, Dict]] = []
    for p in pages:
        text_all = " ".join([p.get("title") or "", p.get("snippet") or "", p.get("source") or ""]).lower()
        code, art, part = _parse_norms_from_text(text_all)
        if not art or art not in target_articles:
            continue
        if _mentions_unrelated_article(text_all, target_articles):
            # нашлась явная «ст. X», не равная целям — отбрасываем
            continue
        sc = _score_item({"title": p.get("title",""), "snippet": p.get("snippet",""),
                          "url": p.get("source",""), "source": p.get("source","")}, targets)
        strong.append((sc, p))

    strong.sort(key=lambda x: (x[0], len((x[1].get("snippet") or ""))), reverse=True)
    strong_kept = [p for s, p in strong[:max_keep]]

    if len(strong_kept) >= min_keep:
        # Убираем дубли по URL
        seen = set()
        out = []
        for p in strong_kept:
            u = p.get("source") or ""
            if not u or u in seen:
                continue
            seen.add(u)
            out.append(p)
        return out

    # 2) FALLBACK: если строгий фильтр дал мало/ничего — мягко ранжируем и берём min_keep
    soft: List[Tuple[int, Dict]] = []
    for p in pages:
        sc = _score_item({"title": p.get("title",""), "snippet": p.get("snippet",""),
                          "url": p.get("source",""), "source": p.get("source","")}, targets)
        soft.append((sc, p))
    soft.sort(key=lambda x: (x[0], len((x[1].get("snippet") or ""))), reverse=True)

    seen = set()
    out = []
    for s, p in soft:
        u = p.get("source") or ""
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(p)
        if len(out) >= max(min_keep, 2):
            break
    return out