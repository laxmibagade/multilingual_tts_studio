import re

MAX_CHARS = 30000
CHUNK_CHARS = 850

CHAPTER_RE = re.compile(
    r"(?im)^\s*(?:#{1,3}\s*)?(?:chapter\s+\d+|अध्याय\s*[\d०-९]+|प्रकरण\s*[\d०-९]+)\s*[:：\-–—.]?\s*.*$"
)


def clean_text(text: str) -> str:
    """Normalize whitespace without removing meaningful Marathi punctuation."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_chapters(text: str) -> list[dict]:
    """
    Split on heading lines like:
      # Chapter 1: Introduction
      अध्याय १: मंगलाचरण
    If no chapter heading is detected, return one default chapter.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    lines = text.splitlines()
    chapters = []
    current_title = "Chapter 1"
    current_lines = []
    found_heading = False

    for line in lines:
        if CHAPTER_RE.match(line.strip()):
            if current_lines and "\n".join(current_lines).strip():
                chapters.append({
                    "title": current_title,
                    "text": clean_text("\n".join(current_lines)),
                })
            current_title = re.sub(r"^\s*#{1,3}\s*", "", line.strip())
            current_lines = []
            found_heading = True
        else:
            current_lines.append(line)

    body = clean_text("\n".join(current_lines))
    if body:
        chapters.append({"title": current_title, "text": body})

    if not found_heading:
        return [{"title": "Full narration", "text": clean_text(text)}]

    # Handle text that begins with a heading and empty body, or leading text.
    return [
        {"title": ch["title"], "text": ch["text"]}
        for ch in chapters if ch["text"]
    ]


def split_long_text(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """Split text at paragraph/sentence boundaries where possible."""
    text = clean_text(text)
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?।॥])\s+|\n+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        pieces = []
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars + 1)
            if cut < max_chars // 2:
                cut = max_chars
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            pieces.append(sentence)

        for piece in pieces:
            candidate = f"{current} {piece}".strip()
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = candidate

    if current:
        chunks.append(current)
    return chunks


def pause_after_chunk(text: str, sentence_pause_ms: int, paragraph_pause_ms: int) -> int:
    stripped = text.rstrip()
    if "\n\n" in text or stripped.endswith(("॥", "।।")):
        return paragraph_pause_ms
    if stripped.endswith(("।", ".", "!", "?")):
        return sentence_pause_ms
    return 150
