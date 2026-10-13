# Multilingual Text-to-Speech Studio — Chapter Upgrade

## Features
- Marathi, Hindi, and English voice selection (where available)
- Chapter detection using headings like `अध्याय १: मंगलाचरण` or `# Chapter 2: Main Story`
- Individual chapter audio files plus one combined narration
- MP3/WAV export
- Adjustable speed and pauses
- SRT subtitles (approximate chapter-level timing for combined SRT, chunk-level timing for individual chapters)
- Download all outputs as one ZIP
- Local metadata history

## Windows setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open `http://localhost:8501`.

## Important
- Internet required for Edge TTS.
- WAV export uses `pydub` and `imageio-ffmpeg`.
- Subtitle timing is approximate, not word-level forced alignment.
- A 30,000-character safety limit is enforced.
- Files and metadata are stored locally in `output/` and `data/`.
- Do not deploy publicly without authentication, per-user storage, cleanup, request limits, and appropriate privacy controls.
