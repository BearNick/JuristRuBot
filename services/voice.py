import os, tempfile, subprocess
from core.config import USE_VOSK
from pydub import AudioSegment

def ogg_to_wav(ogg_path: str) -> str:
    # Convert OGG/OPUS -> WAV PCM16 using ffmpeg via pydub
    audio = AudioSegment.from_file(ogg_path, format="ogg")
    wav_path = tempfile.mktemp(suffix=".wav")
    audio.export(wav_path, format="wav")
    return wav_path

def ensure_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception:
        raise RuntimeError("FFmpeg is required. Install it and ensure it's in PATH.")

def transcribe(ogg_path: str) -> str:
    ensure_ffmpeg()
    wav_path = ogg_to_wav(ogg_path)
    if USE_VOSK:
        from vosk import Model, KaldiRecognizer  # lazy import
        import json as _json
        model = Model(lang="ru")
        rec = KaldiRecognizer(model, 16000)
        rec.SetWords(True)
        # Downsample to 16k mono if needed is handled by pydub export default
        with open(wav_path, "rb") as f:
            data = f.read()
        rec.AcceptWaveform(data)
        result = _json.loads(rec.Result())
        return result.get("text", "").strip()
    else:
        # The higher-level orchestrator (bot.py) will call OpenAI Whisper via nlp.openai_client
        return "__USE_OPENAI_WHISPER__"
