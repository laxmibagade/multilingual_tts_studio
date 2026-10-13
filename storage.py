import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
AUDIO_DIR = ROOT / "output" / "audio"
SUBTITLE_DIR = ROOT / "output" / "subtitles"
HISTORY_FILE = DATA_DIR / "history.json"

for folder in (DATA_DIR, AUDIO_DIR, SUBTITLE_DIR):
    folder.mkdir(parents=True, exist_ok=True)


def load_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_history_item(item: dict):
    history = load_history()
    history.insert(0, item)
    # Limit history metadata growth.
    history = history[:100]
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def new_history_item(audio_name, subtitle_name, language, voice, rate, text_length, audio_format):
    return {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "audio_name": audio_name,
        "subtitle_name": subtitle_name,
        "language": language,
        "voice": voice,
        "rate": rate,
        "text_length": text_length,
        "audio_format": audio_format,
    }
