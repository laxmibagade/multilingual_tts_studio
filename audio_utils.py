import io
import os
import tempfile
from pathlib import Path

import imageio_ffmpeg
from pydub import AudioSegment
from pydub.utils import which

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
AudioSegment.converter = FFMPEG


def mp3_bytes_to_segment(data: bytes) -> AudioSegment:
    return AudioSegment.from_file(io.BytesIO(data), format="mp3")


def silence(milliseconds: int) -> AudioSegment:
    return AudioSegment.silent(duration=max(0, int(milliseconds)), frame_rate=24000)


def export_audio(segment: AudioSegment, output_path: str, fmt: str) -> None:
    fmt = fmt.lower()
    segment.export(output_path, format=fmt)


def segment_duration_ms(segment: AudioSegment) -> int:
    return len(segment)


def timestamp_srt(milliseconds: int) -> str:
    milliseconds = max(0, int(milliseconds))
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"
