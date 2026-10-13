import io
import re
import uuid
import zipfile
from pathlib import Path

import streamlit as st
from pydub import AudioSegment

from audio_utils import export_audio, mp3_bytes_to_segment, segment_duration_ms, silence
from storage import AUDIO_DIR, SUBTITLE_DIR, load_history, save_history_item, new_history_item
from subtitle_utils import make_srt
from text_processing import (
    MAX_CHARS, clean_text, pause_after_chunk, split_chapters, split_long_text
)
from tts_engine import list_voices, synthesize

st.set_page_config(page_title="Multilingual TTS Studio", page_icon="🎙️", layout="wide")

LANGUAGES = {
    "Marathi": "mr-IN",
    "Hindi": "hi-IN",
    "English (India)": "en-IN",
    "English (United States)": "en-US",
    "English (United Kingdom)": "en-GB",
}
RATES = {"Very slow": "-25%", "Slow": "-15%", "Normal": "+0%", "Fast": "+15%", "Very fast": "+25%"}


def safe_filename(name: str) -> str:
    name = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")
    return name[:60] or "chapter"


def generate_chapter(chapter, voice_name, rate, sentence_pause, paragraph_pause, output_format):
    """Synthesize one chapter, preserving chunk timing for approximate SRT."""
    combined = AudioSegment.empty()
    subtitle_items = []
    chunks = split_long_text(chapter["text"])

    for chunk in chunks:
        mp3_data = synthesize(chunk, voice_name, rate)
        part = mp3_bytes_to_segment(mp3_data)
        start_ms = segment_duration_ms(combined)
        combined += part
        end_ms = segment_duration_ms(combined)

        subtitle_items.append({
            "text": chunk,
            "start_ms": start_ms,
            "end_ms": end_ms,
        })
        combined += silence(pause_after_chunk(chunk, sentence_pause, paragraph_pause))

    for i in range(len(subtitle_items) - 1):
        subtitle_items[i]["end_ms"] = subtitle_items[i + 1]["start_ms"]

    return combined, make_srt(subtitle_items), len(chunks)


st.title("🎙️ Multilingual Text-to-Speech Studio")
st.write("Create chapter-wise narration, merge chapters, export MP3/WAV, and download SRT subtitles.")

with st.sidebar:
    st.header("Narration settings")
    language = st.selectbox("Language / accent", list(LANGUAGES.keys()))
    gender = st.radio("Voice gender", ["Female", "Male"], horizontal=True)
    speed_name = st.select_slider("Speaking speed", options=list(RATES), value="Normal")
    sentence_pause = st.slider("Pause after sentence (ms)", 0, 2000, 450, 50)
    paragraph_pause = st.slider("Pause after paragraph / verse (ms)", 200, 4000, 1200, 100)
    output_format = st.radio("Audio format", ["MP3", "WAV"], horizontal=True)
    make_subtitles = st.checkbox("Generate SRT subtitles", value=True)

st.subheader("1. Add your script")
st.markdown(
    "For chapter separation, put each chapter heading on its own line, for example "
    "`अध्याय १: मंगलाचरण` or `# Chapter 2: Main Story`. "
    "If no headings are present, the whole script becomes one chapter."
)
script = st.text_area(
    "Text to narrate",
    height=320,
    placeholder=(
        "अध्याय १: मंगलाचरण\n"
        "॥ श्री गणेशाय नमः ॥\n\n"
        "श्री गजानन महाराज की जय!\n\n"
        "अध्याय २: मुख्य कथा\n"
        "आज आपण भक्तिभावाने..."
    ),
)
uploaded_text = st.file_uploader("Or upload a UTF-8 text file (.txt)", type=["txt"])
if uploaded_text is not None:
    try:
        script = uploaded_text.getvalue().decode("utf-8-sig")
        st.info("Text loaded from uploaded file.")
    except UnicodeDecodeError:
        st.error("Please upload a UTF-8 encoded text file.")

cleaned = clean_text(script)
st.caption(f"Characters: {len(cleaned):,} / {MAX_CHARS:,}")

if len(cleaned) > MAX_CHARS:
    st.error(f"Please keep each generation at or below {MAX_CHARS:,} characters.")
    st.stop()

chapters = split_chapters(script)
st.subheader("2. Chapter preview")
if chapters:
    st.write(f"Detected chapters: **{len(chapters)}**")
    for index, chapter in enumerate(chapters, start=1):
        with st.expander(f"{index}. {chapter['title']} — {len(chapter['text']):,} characters"):
            st.write(chapter["text"][:2500])
            if len(chapter["text"]) > 2500:
                st.caption("Preview truncated.")
else:
    st.info("Enter text to preview chapters.")

st.subheader("3. Select voice")
try:
    voices = list_voices()
    locale = LANGUAGES[language]
    available = [v for v in voices if v.get("Locale") == locale and v.get("Gender") == gender]
    if available:
        voice_labels = {
            f'{v.get("LocalName", v["ShortName"])} ({v["ShortName"]})': v["ShortName"]
            for v in available
        }
        voice_label = st.selectbox("Available voices", list(voice_labels))
        voice_name = voice_labels[voice_label]
    else:
        voice_name = None
        st.warning(f"No {gender.lower()} voice is currently listed for {language}. Try the other gender or language.")
except Exception as exc:
    voice_name = None
    st.error("Could not retrieve voices. Check your internet connection.")
    st.caption(str(exc))

st.warning(
    "Privacy notice: this starter stores generated files on the server. "
    "Do not enter confidential text. On a public deployment without login, "
    "files may be accessible to other visitors. Add authentication and per-user storage before public launch."
)

if st.button("Generate chapter audio + combined narration", type="primary", use_container_width=True):
    if not cleaned:
        st.error("Enter text or upload a text file first.")
    elif not chapters:
        st.error("No text was found.")
    elif not voice_name:
        st.error("Select a voice that is available for this language.")
    else:
        job_id = uuid.uuid4().hex[:10]
        safe_lang = safe_filename(language.lower())
        rate = RATES[speed_name]
        all_audio = AudioSegment.empty()
        all_srt_items = []
        chapter_outputs = []
        progress = st.progress(0)
        status = st.empty()
        total_chunks = sum(max(1, len(split_long_text(c["text"]))) for c in chapters)
        completed_chunks = 0

        try:
            for chapter_index, chapter in enumerate(chapters, start=1):
                status.write(f"Generating chapter {chapter_index}/{len(chapters)}: {chapter['title']}")
                chapter_audio, chapter_srt, chunk_count = generate_chapter(
                    chapter, voice_name, rate, sentence_pause, paragraph_pause, output_format
                )

                chapter_slug = safe_filename(chapter["title"])
                chapter_audio_name = f"{job_id}_{chapter_index:02d}_{chapter_slug}.{output_format.lower()}"
                chapter_audio_path = AUDIO_DIR / chapter_audio_name
                export_audio(chapter_audio, str(chapter_audio_path), output_format.lower())

                chapter_srt_name = ""
                if make_subtitles:
                    chapter_srt_name = f"{job_id}_{chapter_index:02d}_{chapter_slug}.srt"
                    (SUBTITLE_DIR / chapter_srt_name).write_text(chapter_srt, encoding="utf-8")

                chapter_outputs.append({
                    "title": chapter["title"],
                    "audio_name": chapter_audio_name,
                    "audio_path": str(chapter_audio_path),
                    "srt_name": chapter_srt_name,
                    "srt_text": chapter_srt if make_subtitles else "",
                    "duration_ms": len(chapter_audio),
                })

                # Combined narration includes a longer pause between chapters.
                base_ms = len(all_audio)
                if len(all_audio) > 0:
                    all_audio += silence(paragraph_pause)
                    base_ms = len(all_audio)

                all_audio += chapter_audio
                if make_subtitles:
                    # Rebase chapter SRT items by parsing the known chunk timings again.
                    offset = base_ms
                    local_chunks = split_long_text(chapter["text"])
                    # Approximate chapter-level SRT is retained separately; combined SRT
                    # uses chapter-level blocks with duration proportional to chapter audio.
                    all_srt_items.append({
                        "text": chapter["title"] + "\n" + chapter["text"],
                        "start_ms": offset,
                        "end_ms": offset + len(chapter_audio),
                    })

                completed_chunks += chunk_count
                progress.progress(chapter_index / len(chapters))

            combined_name = f"narration_{safe_lang}_{job_id}.{output_format.lower()}"
            combined_path = AUDIO_DIR / combined_name
            export_audio(all_audio, str(combined_path), output_format.lower())

            combined_srt_name = ""
            combined_srt = ""
            if make_subtitles:
                combined_srt_name = f"narration_{safe_lang}_{job_id}.srt"
                combined_srt = make_srt(all_srt_items)
                (SUBTITLE_DIR / combined_srt_name).write_text(combined_srt, encoding="utf-8")

            save_history_item(new_history_item(
                audio_name=combined_name,
                subtitle_name=combined_srt_name,
                language=language,
                voice=voice_name,
                rate=rate,
                text_length=len(cleaned),
                audio_format=output_format,
            ))

            st.session_state["chapter_outputs"] = chapter_outputs
            st.session_state["combined_path"] = str(combined_path)
            st.session_state["combined_name"] = combined_name
            st.session_state["combined_format"] = output_format
            st.session_state["combined_srt"] = combined_srt
            st.session_state["combined_srt_name"] = combined_srt_name
            status.success("All chapters and combined narration generated successfully!")

        except Exception as exc:
            st.error("Generation failed. Check your internet connection and try a shorter script.")
            st.caption(f"Technical details: {exc}")

if st.session_state.get("combined_path"):
    combined_path = Path(st.session_state["combined_path"])
    st.subheader("4. Combined narration")
    if combined_path.exists():
        mime = "audio/wav" if st.session_state["combined_format"] == "WAV" else "audio/mpeg"
        audio_data = combined_path.read_bytes()
        st.audio(audio_data, format=mime)
        st.download_button(
            "Download complete narration",
            data=audio_data,
            file_name=st.session_state["combined_name"],
            mime=mime,
            use_container_width=True,
        )

    if st.session_state.get("combined_srt"):
        st.download_button(
            "Download combined SRT",
            data=st.session_state["combined_srt"].encode("utf-8"),
            file_name=st.session_state["combined_srt_name"],
            mime="text/plain",
            use_container_width=True,
        )

    st.subheader("5. Individual chapters")
    for chapter in st.session_state.get("chapter_outputs", []):
        with st.expander(chapter["title"]):
            chapter_path = Path(chapter["audio_path"])
            if chapter_path.exists():
                chapter_data = chapter_path.read_bytes()
                mime = "audio/wav" if st.session_state["combined_format"] == "WAV" else "audio/mpeg"
                st.audio(chapter_data, format=mime)
                st.download_button(
                    f"Download {chapter['title']}",
                    data=chapter_data,
                    file_name=chapter["audio_name"],
                    mime=mime,
                    key=f"audio_{chapter['audio_name']}",
                )
            if chapter.get("srt_text"):
                st.download_button(
                    f"Download subtitles: {chapter['title']}",
                    data=chapter["srt_text"].encode("utf-8"),
                    file_name=chapter["srt_name"],
                    mime="text/plain",
                    key=f"srt_{chapter['srt_name']}",
                )

    # Convenient ZIP with chapter files + combined files.
    if st.button("Prepare ZIP of all generated files"):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            if combined_path.exists():
                zf.write(combined_path, arcname=st.session_state["combined_name"])
            if st.session_state.get("combined_srt"):
                zf.writestr(st.session_state["combined_srt_name"], st.session_state["combined_srt"])
            for chapter in st.session_state.get("chapter_outputs", []):
                p = Path(chapter["audio_path"])
                if p.exists():
                    zf.write(p, arcname=chapter["audio_name"])
                if chapter.get("srt_text"):
                    zf.writestr(chapter["srt_name"], chapter["srt_text"])
        st.download_button(
            "Download ZIP bundle",
            data=zip_buffer.getvalue(),
            file_name="tts_chapters_bundle.zip",
            mime="application/zip",
            key="download_bundle",
        )

st.divider()
st.subheader("6. Generation history")
st.caption("History records settings and filenames, not the full script.")
history = load_history()
if history:
    st.dataframe(
        [
            {
                "Created": h.get("created_at"),
                "Language": h.get("language"),
                "Voice": h.get("voice"),
                "Speed": h.get("rate"),
                "Characters": h.get("text_length"),
                "Format": h.get("audio_format"),
                "Audio file": h.get("audio_name"),
                "Subtitle file": h.get("subtitle_name") or "—",
            }
            for h in history
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No generated files yet.")

st.caption("SRT timing is approximate. Word-level synchronization requires a separate alignment process.")
