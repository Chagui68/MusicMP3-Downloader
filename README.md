# MusicMP3 → Note Block Converter

Convert any song to Minecraft Note Block Studio (`.nbs`) format with **source separation** and **multi-layer instrument assignment**.

## Quick start

```sh
# 1. Activate the virtual environment (required)
source .venv/bin/activate

# 2. Run the converter
musicmp3 "Never Gonna Give You Up"

# Or use the web interface
musicmp3-gui
# → Opens http://localhost:7860 in your browser
```

> ML models (Demucs + basic-pitch) are already installed in `.venv`. If you need to install them from scratch, see [Installation](#installation).

## Pipeline

```
YouTube / MP3 → Demucs (source separation) → stems (bass, drums, vocals, other)
              → basic-pitch (audio → MIDI per stem)
              → MIDI → NBS (octave compression, instrument mapping)
              → .nbs file with dedicated layers
```

Each stem gets its own NBS layer with the appropriate instrument:
- **Bass** → Bass Drum
- **Drums** → Click
- **Vocals** → Flute
- **Other** → Piano

## Requirements

- Python 3.10+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (on PATH)
- [FFmpeg](https://ffmpeg.org/) (on PATH)

## Installation

```sh
# Clone and install
git clone <repo>
cd MusicMP3-Downloader
python3 -m venv .venv
.venv/bin/pip install -e .

# For best quality (ML models):
.venv/bin/pip install demucs torch torchaudio basic-pitch onnxruntime resampy pretty-midi mir-eval
```

## Usage

### CLI

```sh
# Download from YouTube + convert
.venv/bin/musicmp3 "Never Gonna Give You Up"

# Use a local file
.venv/bin/musicmp3 --file path/to/song.mp3

# Download only (skip conversion)
.venv/bin/musicmp3 --download-only "Song Name"
```

### Web UI

```sh
.venv/bin/musicmp3-gui
# Opens at http://localhost:7860
```

## Output

- `downloads/` — MP3 files
- `nbs_songs/` — NBS files (ready to open in OpenNoteBlockStudio or use in Minecraft)

## Quality tiers

| Tier | Setup | Result |
|------|-------|--------|
| **Best** | Demucs + basic-pitch | Full source separation, 4 layers, instrument assignment |
| **Good** | basic-pitch only | Single layer, no stem separation |
| **Basic** | librosa FFT fallback | Monophonic pitch detection, single layer |

## Project structure

```
musicmp3/
├── cli.py           # CLI entry point
├── converter.py     # Pipeline orchestrator
├── downloader.py    # YouTube download (yt-dlp)
├── gui.py           # Gradio web interface
├── midi_to_nbs.py   # MIDI → NBS conversion
├── nbs.py           # NBS binary format writer
├── separator.py     # Demucs source separation
└── transcriber.py   # Audio → MIDI (basic-pitch / FFT)
pyproject.toml
```
