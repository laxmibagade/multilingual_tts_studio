
import io
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from pydub import AudioSegment

# Use the FFmpeg executable bundled by imageio-ffmpeg.
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
AudioSegment.converter = FFMPEG


def mp3_bytes_to_segment(data: bytes) -> AudioSegment:
    """Decode MP3 bytes through FFmpeg without requiring ffprobe."""
    if not data:
        raise ValueError("The TTS engine returned empty audio data.")

    with tempfile.TemporaryDirectory() as temp_dir:
        wav_path = Path(temp_dir) / "decoded.wav"

        result = subprocess.run(
            [
                FFMPEG,
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", "pipe:0",
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "24000",
                "-ac", "1",
                str(wav_path),
            ],
            input=data,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
        )

        if result.returncode != 0 or not wav_path.exists():
            details = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"MP3 decoding failed: {details}")

        return AudioSegment.from_wav(str(wav_path))


def silence(milliseconds: int) -> AudioSegment:
    """Generate silence at 24 kHz."""
    return AudioSegment.silent(
        duration=max(0, int(milliseconds)),
        frame_rate=24000,
    )


def export_audio(
    segment: AudioSegment,
    output_path: str,
    fmt: str,
) -> None:
    """Export WAV or MP3 using the configured FFmpeg executable."""
    fmt = fmt.lower()

    if fmt not in ("mp3", "wav"):
        raise ValueError(f"Unsupported audio format: {fmt}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    segment.export(
        output_path,
        format=fmt,
        parameters=["-ar", "24000", "-ac", "1"],
    )


def segment_duration_ms(segment: AudioSegment) -> int:
    return len(segment)


def timestamp_srt(milliseconds: int) -> str:
    milliseconds = max(0, int(milliseconds))
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)

    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"
