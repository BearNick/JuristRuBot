from typing import List, Dict
from openai import OpenAI
from core.config import OPENAI_API_KEY, OPENAI_MODEL
from core.logger import log

_client = None

def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client

def refine_query(user_question: str) -> str:
    """
    Переформулировка в краткий поисковый запрос (<=120 знаков).
    """
    system = (
        "Переформулируй вопрос в юридический поисковый запрос для РФ (<=120 знаков), "
        "добавив ключи: кодекс, статья, часть, термин. Ответ — только строка запроса."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_question.strip()[:1000]},
    ]
    try:
        resp = client().chat.completions.create(
            model=OPENAI_MODEL, messages=messages, temperature=0.2, max_tokens=80
        )
        return (resp.choices[0].message.content or "").strip() or user_question
    except Exception as e:
        log.warning("refine_query failed: %s", e)
        return user_question

def qualify_issue(user_question: str) -> str:
    """
    Квалификация: предложи 1–3 самых вероятных НОРМЫ (кодекс, статья, часть) + ключевые слова для поиска.
    Ответ — одна строка, например:
    `КоАП РФ ст. 20.1 ч.1 мелкое хулиганство; КоАП РФ ст. 6.1.1 побои; УК РФ ст. 213 хулиганство`
    """
    system = (
        "Определи самые вероятные НОРМЫ РФ (кодекс, статья, часть) для запроса. "
        "Верни 1 строку: 1–3 вариантов через ';', каждый: "
        "'{Кодекс} ст. X ч. Y {краткий термин}'. Без пояснений."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_question.strip()[:1000]},
    ]
    try:
        resp = client().chat.completions.create(
            model=OPENAI_MODEL, messages=messages, temperature=0.1, max_tokens=120
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        log.warning("qualify_issue failed: %s", e)
        return ""

def chat_answer(system_prompt: str, user_question: str, context_chunks: List[Dict]) -> str:
    # context_chunks: [{"source": url, "title": str, "snippet": str}]
    ctx_lines = []
    for c in context_chunks:
        ctx_lines.append(
            f"SOURCE: {c.get('source','')}\nTITLE: {c.get('title','')}\nEXCERPT: {c.get('snippet','')}"
        )
    ctx_text = "\n\n".join(ctx_lines) or "(no-context)"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Вопрос: {user_question}\n\nКонтекст:\n{ctx_text}"},
    ]
    log.info("Sending to OpenAI with %d context chunks", len(context_chunks))
    resp = client().chat.completions.create(
        model=OPENAI_MODEL, messages=messages, temperature=0.2, max_tokens=700
    )
    return (resp.choices[0].message.content or "").strip()

def transcribe_ogg_pcm16(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            tr = client().audio.transcriptions.create(model="whisper-1", file=f)
        return (tr.text or "").strip()
    except Exception as e:
        log.warning("whisper transcription failed: %s", e)
        return ""
