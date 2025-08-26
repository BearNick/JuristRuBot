# coding: utf-8
from typing import Dict
from openai import OpenAI
from core.config import OPENAI_API_KEY, OPENAI_MODEL
from core.logger import log

_client = None
def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client

SYSTEM_BASE = (
    "Ты — помощник-юрист РФ. Твоя задача — подготовить ПЛАН ПОИСКА и КАНДИДАТЫ К НОРМАМ.\n"
    "1) Сначала определи юридическую квалификацию бытового описания (разговорные формулировки надо перевести в термины права: "
    "напр. «ходить голым в общественном месте» → «мелкое хулиганство (КоАП РФ ст. 20.1 ч.1)»; "
    "«уехал с места аварии» → «оставление места ДТП (КоАП РФ ст. 12.27 ч.2)»; и т.п.).\n"
    "2) Сформируй пакет поисковых запросов для РФ:\n"
    "   • Q_STRICT — узкий запрос с точной нормой (Кодекс, статья, часть) + ключевые юридические слова;\n"
    "   • Q_SEMI — средний (норма + ключи по ситуации/терминам);\n"
    "   • Q_BROAD — широкий (синонимы/общее название правонарушения), но юридически осмысленный;\n"
    "   • Q_ALT — 1–3 альтернативы (близкие квалификации или иные статьи), если уместно;\n"
    "   • QUAL — список до 3 кандидатов-норм в формате: «Кодекс;Статья;Часть;Короткий_термин».\n"
    "Верни ЧИСТЫЙ JSON без пояснений строго такого вида:\n"
    "{\"Q_STRICT\":\"...\",\"Q_SEMI\":\"...\",\"Q_BROAD\":\"...\",\"Q_ALT\":[\"...\",\"...\"],\"QUAL\":[\"Кодекс;Ст;Ч;Термин\", ...]}"
)

SYSTEM_FORCE = SYSTEM_BASE + (
    "\nВажно: форсируй привязку к конкретным нормам. Если вопрос разговорный, ОБЯЗАТЕЛЬНО дай хотя бы одну конкретную норму "
    "в QUAL (например, КоАП РФ ст. 20.1 ч.1; КоАП РФ ст. 12.27 ч.2; УК РФ ст. 213 и т.д.)."
)

def plan_queries(user_question: str, force: bool = False) -> Dict:
    """
    Возвращает словарь:
    {Q_STRICT:str, Q_SEMI:str, Q_BROAD:str, Q_ALT:list[str], QUAL:list[str]}
    """
    system = SYSTEM_FORCE if force else SYSTEM_BASE
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_question.strip()[:600]},
    ]
    try:
        resp = client().chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        import json
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        log.warning("plan_queries failed: %s", e)
        data = {}

    # Санити-значения
    data.setdefault("Q_STRICT", user_question)
    data.setdefault("Q_SEMI", user_question)
    data.setdefault("Q_BROAD", user_question)
    data.setdefault("Q_ALT", [])
    data.setdefault("QUAL", [])
    return data