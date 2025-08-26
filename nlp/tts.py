import tempfile
import os
from pydub import AudioSegment
from openai import OpenAI
from core.config import OPENAI_API_KEY
from core.logger import log

OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_TTS_VOICE = "alloy"

_client = None
def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client

def synthesize_to_ogg(text: str) -> str:
    short = (text or "").strip()
    if not short:
        raise ValueError("Empty text for TTS")
    short = short[:800]

    mp3_path = tempfile.mktemp(suffix=".mp3")
    ogg_path = tempfile.mktemp(suffix=".ogg")

    try:
        with client().audio.speech.with_streaming_response.create(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_TTS_VOICE,
            input=short,
            format="mp3",
        ) as response:
            response.stream_to_file(mp3_path)
    except Exception as e:
        log.warning("TTS request failed: %s", e)
        raise

    try:
        audio = AudioSegment.from_file(mp3_path, format="mp3")
        audio.export(ogg_path, format="ogg", codec="libopus", parameters=["-b:a", "64k"])
    except Exception as e:
        log.warning("FFmpeg/pydub failed: %s", e)
        raise
    finally:
        try:
            os.remove(mp3_path)
        except Exception:
            pass

    return ogg_path