from audio_utils import timestamp_srt


def make_srt(items: list[dict]) -> str:
    """
    items: list of {"text": str, "start_ms": int, "end_ms": int}.
    Chunk-level subtitles are approximate; they are not word-level captions.
    """
    blocks = []
    for index, item in enumerate(items, start=1):
        start = timestamp_srt(item["start_ms"])
        end = timestamp_srt(max(item["start_ms"] + 1, item["end_ms"]))
        text = item["text"].strip()
        blocks.append(f"{index}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")
