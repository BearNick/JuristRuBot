# coding: utf-8
import asyncio
import datetime
import tempfile

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, ContentType
from aiogram.filters import CommandStart, Command

from core.config import (
    TELEGRAM_BOT_TOKEN,
    OPENAI_MODEL,
    PAYMENT_PROVIDER_TOKEN,
    PRICE_RUB_SUBUNITS,
    POSTPAY_MODE,
    STRICT_VALIDATION,
    REQUIRE_SOURCES_TO_ANSWER,
)
from core.logger import log

from services.rate_limit import clamp_text
from services.voice import transcribe as transcribe_voice
from nlp.openai_client import chat_answer, transcribe_ogg_pcm16
from nlp.query_planner import plan_queries
from nlp.intent import classify_intent

from legal.law_search import multi_query_search
from legal.law_fetcher import fetch_page
from legal.answer_formatter import format_answer
from legal.validator import has_strict_legal_quality

# ---------- PROMPT ----------
with open("nlp/prompt_legal_ru.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read().replace(
        "__TODAY__", datetime.date.today().strftime("%d.%m.%Y")
    )

# ---------- BOT ----------
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

WELCOME = (
    "Привет! Я юридический помощник по праву РФ. Опишите ситуацию (до 1000 символов). "
    "Можно голосом. Я подберу нормы и кратко объясню, что делать."
)

@dp.message(CommandStart())
async def start(m: Message):
    await m.answer(WELCOME)

@dp.message(Command("help"))
async def help_cmd(m: Message):
    await m.answer(WELCOME + "\n\nКоманды: /start, /help, /buy (оплата)")

# ---------- PAYMENTS ----------
@dp.message(Command("buy"))
async def buy_cmd(m: Message):
    if not PAYMENT_PROVIDER_TOKEN:
        await m.answer("Платёжный провайдер не настроен. Обратитесь к администратору.")
        return
    title = "Юридическая справка"
    desc = "Оплата одной справки (текст)."
    prices = [LabeledPrice(label="Справка", amount=PRICE_RUB_SUBUNITS)]
    await bot.send_invoice(
        chat_id=m.chat.id,
        title=title,
        description=desc,
        payload=f"postpay:{m.from_user.id}:{m.message_id}",
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        max_tip_amount=0,
        start_parameter="buy_legal_note",
    )

@dp.pre_checkout_query()
async def process_pre_checkout_q(pre_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_q.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(m: Message):
    await m.answer("Спасибо за оплату ✅")

# ---------- CORE ANSWER ----------
async def handle_question(text: str) -> str:
    """
    Фильтр намерения → если LEGAL — полный цикл, если PARALEGAL — коротко,
    если OFFTOPIC — вежливое пояснение про специализацию.
    """
    from legal.relevance import filter_and_rank_pages  # локальный импорт, чтобы не тянуть лишнее на старте

    q_raw = (text or "").strip()
    q = clamp_text(q_raw)

    intent = classify_intent(q_raw)
    log.info("INTENT decided: %s | text='%s'", intent, q_raw[:200])

    # --- OFFTOPIC: сухо, без поиска ---
    if intent == "OFFTOPIC":
        return ("Я юридический помощник по праву РФ. Отвечаю на вопросы по КоАП, УК, ГК, трудовому, налоговому и др. "
                "Опишите ситуацию или задайте юридический вопрос — я подберу нормы и подскажу шаги.")

    # --- PARALEGAL: короткий ответ без тяжёлого поиска ---
    if intent == "PARALEGAL":
        low = q_raw.lower()
        if "курс" in low and ("доллар" in low or "usd" in low or "евро" in low or "eur" in low):
            return ("Это около-правовой вопрос. Актуальные официальные курсы публикует Банк России: cbr.ru/currency_base/daily/. "
                    "Если курс нужен для расчётов по договору/пошлине — укажите дату и правовой контекст, подскажу, какую норму применять.")
        return ("Это ближе к справочному вопросу. Я фокусируюсь на праве РФ. "
                "Если подскажете юридический контекст (норма/статья/ситуация), дам точные нормы и шаги.")

    # --- LEGAL: полный цикл ---
    plan = plan_queries(q, force=False)
    queries: list[str] = []
    for k in ("Q_STRICT", "Q_SEMI", "Q_BROAD"):
        if plan.get(k):
            queries.append(plan[k])
    for alt in plan.get("Q_ALT", []):
        if alt:
            queries.append(alt)
    if not queries:
        queries = [q]

    results = multi_query_search(queries)

    # сбор страниц
    pages_raw = []
    for r in results[:10]:
        try:
            page = fetch_page(r["url"])
            snippet = page.get("snippet") or page["text"][:1800]
            if not snippet or len(snippet) < 120:
                continue
            pages_raw.append({"source": page["url"], "title": page["title"], "snippet": snippet})
        except Exception as e:
            log.warning("fetch failed %s: %s", r["url"], e)

    # строгий фильтр по QUAL
    pages = filter_and_rank_pages(
        pages_raw,
        plan.get("QUAL", []),
        min_keep=2,
        max_keep=6,
        strict=True,
    )
    used = [{"url": p["source"], "title": p["title"]} for p in pages]

    # генерация ответа (даже если источников мало — даём справку)
    answer = chat_answer(SYSTEM_PROMPT, q_raw, pages)

    # индикатор уверенности
    try:
        ok = has_strict_legal_quality(answer)
    except Exception:
        ok = False
    conf = "высокая" if (len(used) >= 3 and ok) else ("средняя" if used else "низкая")

    if not used:
        answer = "Предварительная справка (источники не подтверждены мгновенно):\n" + answer

    answer = f"Уровень уверенности: {conf}.\n\n{answer}"
    return format_answer(answer, used)

# ---------- MESSAGE HANDLERS ----------
@dp.message(F.text)
async def text_message(m: Message):
    try:
        reply = await handle_question(m.text or "")
    except Exception as e:
        log.exception("handle_question failed (text): %s", e)
        reply = ("Не получилось быстро получить выдержки из баз. "
                 "Могу дать предварительную правовую оценку — сформулируйте ситуацию (кодекс/статья/часть — если знаете).")
    await m.answer(reply)
    if POSTPAY_MODE and PAYMENT_PROVIDER_TOKEN:
        # мягкий пинг на оплату после ответа
        try:
            await buy_cmd(m)
        except Exception as e:
            log.warning("buy_cmd failed: %s", e)

@dp.message(F.voice | F.audio)
async def voice_message(m: Message):
    try:
        file = await m.bot.get_file(m.voice.file_id if m.voice else m.audio.file_id)
        ogg_path = tempfile.mktemp(suffix=".ogg")
        await m.bot.download_file(file.file_path, ogg_path)

        text = transcribe_voice(ogg_path)
        if text == "__USE_OPENAI_WHISPER__":
            text = transcribe_ogg_pcm16(ogg_path)

        if not text.strip():
            await m.answer("Не удалось распознать речь. Попробуйте ещё раз.")
            return

        reply = await handle_question(text)
    except Exception as e:
        log.exception("handle_question failed (voice): %s", e)
        reply = ("Не получилось распознать/обработать голос. "
                 "Пришлите, пожалуйста, коротким текстом (до 500 символов).")
    await m.answer(reply)
    if POSTPAY_MODE and PAYMENT_PROVIDER_TOKEN:
        try:
            await buy_cmd(m)
        except Exception as e:
            log.warning("buy_cmd failed: %s", e)

# ---------- ENTRY ----------
def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    log.info(
        "Starting bot with model=%s | STRICT_VALIDATION=%s | REQUIRE_SOURCES_TO_ANSWER=%s | POSTPAY=%s",
        OPENAI_MODEL, STRICT_VALIDATION, REQUIRE_SOURCES_TO_ANSWER, POSTPAY_MODE
    )
    asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    main()
