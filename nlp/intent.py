# coding: utf-8
"""
Классификатор намерений:
  LEGAL     — строго правовой вопрос по праву РФ
  PARALEGAL — около-правовой (банки/курсы/общие справки), но не «привет»
  OFFTOPIC  — мета-вопросы ("что ты можешь", "кто ты") и явный оффтоп

Логика:
1) Явные OFFTOPIC шаблоны.
2) Сильные юридические эвристики (расширенные русские стемы).
3) Слабые околоправовые эвристики — СРАБАТЫВАЮТ ТОЛЬКО ЕСЛИ НЕ БЫЛО ЮР.ПРИЗНАКОВ.
4) Короткие паттерны "что будет/штраф/наказание" -> LEGAL.
5) Если сомнение — LLM-классификатор (ультракороткий), а затем дефолт LEGAL.
"""

from typing import Literal
import os, re
from nlp.openai_client import chat_answer
from core.logger import log

Intent = Literal["LEGAL", "PARALEGAL", "OFFTOPIC"]

INTENT_DEBUG = os.getenv("INTENT_DEBUG", "false").lower() == "true"

# --- OFFTOPIC шаблоны (мета/общение) ---
OFFTOPIC_PATTERNS = [
    r"\b(кто ты|кто вы|что ты можешь|что умеешь|что вы умеете|кто твой автор|как дела)\b",
    r"\b(привет|здорово|добрый день|доброе утро|добрый вечер|спасибо)\b",
]

# --- Сильные юридические индикаторы (стемы/слова) ---
LEGAL_KEYWORDS = [
    # общие правовые
    r"\bзакон\b", r"\bнорм[аи]\b", r"\bкодекс\b", r"\bст\.?\s*\d+", r"\bстать[ьяи]\b", r"\bчаст[ьи]\b",
    r"\bответственност[ьи]\b", r"\bнаказани[ея]\b", r"\bштраф(ы|а|ов)?\b",
    r"\bсуд\b", r"\bиск\b", r"\bжалоб[аи]\b", r"\bпротокол\b", r"\bпостановлени[ея]\b",
    r"\bадминистративн\w*\b", r"\bуголовн\w*\b", r"\bгражданск\w*\b", r"\bтрудов\w*\b", r"\bсемейн\w*\b",
    r"\bгибдд\b", r"\bдтп\b", r"\bроспотребнадзор\b", r"\bпристав\w*\b",
    # УК — типовые составы
    r"\bубийств\w*\b", r"\bугроз\w*\b", r"\bкраж\w*\b", r"\bграбеж\w*\b", r"\bразбой\w*\b",
    r"\bмошеннич\w*\b", r"\bнаркотик\w*\b", r"\bсбы(т|том)\b", r"\bхранени\w*\b",
    r"\bпобои\b", r"\bвзятк\w*\b",
    # КоАП/ПДД
    r"\bпревышен[ие]\s+скорост[ьи]\b", r"\bлишени\w*\s+прав\b", r"\bалкогол\b", r"\bопьянени\w*\b",
    r"\bстоянк\w*\b", r"\bпарковк\w*\b",
    # семейное/гражданское
    r"\bалименты\b", r"\bразвод\b", r"\bнаследств\w*\b", r"\bопек\w*\b", r"\bдарени\w*\b",
    r"\bипотек\w*\b", r"\bаренд\w*\b", r"\bкупл[яе]-?продаж\w*\b",
    # миграция/труд
    r"\bпатент\b", r"\bвид на жительств\w*\b", r"\bувольнени\w*\b", r"\bдисциплинарн\w*\b",
]

# --- Околоправовые признаки (срабатывают только если нет LEGAL) ---
PARALEGAL_HINTS = [
    r"\bкурс(ы)?\b", r"\bдоллар(а|ов)?\b", r"\bевро\b", r"\busd\b", r"\beur\b", r"\bцб(р| РФ)?\b",
    r"\bпогода\b", r"\bрецепт\b", r"\bновост(и|ь)\b",
    r"\bадрес\b", r"\bтелефон\b", r"\bгде найти\b", r"\bкак добраться\b",
    r"\bинструкция\b", r"\bкак сделать\b", r"\bлайфхак\b",
    r"\bбанк\w*\b", r"\bкарта\b", r"\bперевод\b", r"\bплатеж\b", r"\bвклад\b",
]

# --- Триггеры "короткого" LEGAL ---
LEGAL_SHORT_TRIGGERS = [
    r"\bчто будет( если)?\b",
    r"\bможно ли\b",
    r"\bштраф за\b",
    r"\bнаказани[ея] за\b",
    r"\bлишени\w* прав\b",
    r"\b(\d{2,3})\s*км/?ч\b",
]

LLM_INTENT_SYSTEM = (
    "Классифицируй пользовательский запрос на русском в одну метку: "
    "LEGAL (строго правовой вопрос по праву РФ), "
    "PARALEGAL (справочный/около-правовой: банки, курсы, инструкции), "
    "OFFTOPIC (приветствия, «кто ты», бытовые темы). "
    "Ответь ТОЛЬКО меткой без пояснений."
)

def _m(text: str, patterns: list[str]) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t) for p in patterns)

def classify_intent(text: str) -> Intent:
    t = (text or "").strip()
    if not t:
        if INTENT_DEBUG: log.info("INTENT=OFFTOPIC (empty)")
        return "OFFTOPIC"

    # 1) OFFTOPIC (мета/общение)
    if _m(t, OFFTOPIC_PATTERNS):
        if INTENT_DEBUG: log.info("INTENT=OFFTOPIC (meta)")
        return "OFFTOPIC"

    # 2) Сильные юридические признаки
    if _m(t, LEGAL_KEYWORDS):
        if INTENT_DEBUG: log.info("INTENT=LEGAL (heuristics strong)")
        return "LEGAL"

    # 3) Короткие триггеры LEGAL (что будет/штраф/км/ч и т.п.)
    if _m(t, LEGAL_SHORT_TRIGGERS):
        if INTENT_DEBUG: log.info("INTENT=LEGAL (short trigger)")
        return "LEGAL"

    # 4) Околоправовые только если нет юр.признаков
    if _m(t, PARALEGAL_HINTS):
        if INTENT_DEBUG: log.info("INTENT=PARALEGAL (paralegal hints)")
        return "PARALEGAL"

    # 5) LLM-классификатор как страховка
    try:
        lab = (chat_answer(LLM_INTENT_SYSTEM, t, context=[]) or "").strip().upper()
        if lab in ("LEGAL", "PARALEGAL", "OFFTOPIC"):
            if INTENT_DEBUG: log.info("INTENT=%s (LLM)", lab)
            return lab  # type: ignore
    except Exception as e:
        if INTENT_DEBUG: log.warning("INTENT LLM failed: %s", e)

    # 6) Дефолт — LEGAL (лучше «попробовать помочь», чем отфутболить)
    if INTENT_DEBUG: log.info("INTENT=LEGAL (default)")
    return "LEGAL"