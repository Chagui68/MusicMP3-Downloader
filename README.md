# MusicMP3 — Minecraft Note Block Converter

Convert any audio song to Minecraft Note Block Studio (.nbs) format with a trainable AI model that learns from your conversions.

## Features

- **Automatic conversion** of MP3 / WAV / FLAC to NBS
- **Trainable AI model** that improves with every song
- **Multiple instruments** (Piano, Bass, Snare, Guitar, etc.)
- **Interactive piano roll** with synchronized playhead
- **Smart note optimization** via spectral analysis
- **Web UI, GUI, and CLI** interfaces
- **YouTube download** built-in

## Quick Start

### Prerequisites

- Python 3.10+
- FFmpeg (for audio processing)

### Install

```bash
git clone <repo-url>
cd musicmp3-converter

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS

# Install with server support
pip install -e ".[server]"

# For full install (GUI + ML separation):
pip install -e ".[full,server]"
```

### Setup the model

The repository includes a pre-trained `profile.json` (10 songs, 40k+ notes):

```bash
# Copy the pre-trained model to your user config directory
mkdir -p ~/.musicmp3
cp profile.json ~/.musicmp3/profile.json
```

### Start the server

```bash
musicmp3-server
# or: python -m musicmp3.server
```

Open **http://127.0.0.1:8000** in your browser.

## Usage

### Convert a song

1. **Upload audio** — drag a file or paste a YouTube URL
2. **Configure** — note range, transpose, mode
3. **Convert** — click "Convert audio -> NBS"
4. **Edit** — adjust notes on the piano roll
5. **Download** — export to `.nbs` for Minecraft

### Train the model

The model improves automatically with each conversion:

1. Upload NBS + Audio pairs in the "Train model" section
2. Click "Upload pair" for each song
3. Click "Retrain" to update the model

The pre-trained model ships with `profile.json` and works out of the box.

### CLI

```bash
# Convert a local file
musicmp3 --file song.mp3 -o output/

# Download and convert from YouTube
musicmp3 "https://youtube.com/watch?v=..."

# Download only
musicmp3 "song name" --download-only
```

### GUI

```bash
musicmp3-gui
```

## Commands

| Command | Description |
|---------|-------------|
| `musicmp3` | CLI converter |
| `musicmp3-server` | Web server (FastAPI) |
| `musicmp3-gui` | Gradio GUI |
| `python train_with_real_audio.py` | Train from YouTube songs |
| `python train_20_more.py` | Train with extended dataset |

## Supported Instruments

| ID | Instrument | Range |
|----|-----------|-------|
| 0  | Piano     | 0-87  |
| 1  | Bass Drum | 0-87  |
| 2  | Snare     | 0-87  |
| 3  | Click     | 0-87  |
| 4  | Guitar    | 0-87  |
| 5  | Bass      | 0-87  |
| 6  | Bell      | 0-87  |
| 7  | Chime     | 0-87  |
| 8  | Flute     | 0-87  |
| 9  | Xylophone | 0-87  |
| 10 | Iron Xylo | 0-87  |
| 11 | Cow Bell  | 0-87  |

## Project Structure

```
musicmp3-converter/
├── musicmp3/               # Core library
│   ├── server.py           # FastAPI web server
│   ├── converter.py        # Audio-to-NBS conversion
│   ├── nbs.py              # NBS file manipulation
│   ├── nbs_analyzer.py     # Training & audio analysis
│   ├── nbs_optimizer.py    # Note optimization
│   ├── nbs_visualizer.py   # Piano roll rendering
│   ├── nbs_playback.py     # NBS audio playback
│   ├── transcriber.py      # Audio-to-MIDI
│   ├── separator.py        # Stem separation (Demucs)
│   ├── downloader.py       # YouTube audio download
│   ├── midi_to_nbs.py      # MIDI-to-NBS conversion
│   ├── cli.py              # CLI entrypoint
│   ├── gui.py              # Gradio GUI
│   └── static/             # Web frontend
│       ├── index.html
│       ├── app.js
│       ├── canvas.js
│       ├── api.js
│       └── style.css
├── profile.json            # Pre-trained model
├── pyproject.toml          # Project config & dependencies
├── requirements.txt        # Pip dependencies
├── train_with_real_audio.py
├── auto_train_model.py
├── bulk_train.py
├── setup_model.sh
├── export_model.sh
└── import_model.sh
```

## Dependencies

### Core
- `mido` — MIDI file handling
- `soundfile` — Audio file I/O
- `numpy` — Numerical processing
- `matplotlib` — Piano roll visualization
- `yt-dlp` — YouTube audio download
- `python-multipart` — File uploads

### Server
- `fastapi` — Web framework
- `uvicorn` — ASGI server

### Full (optional)
- `gradio` — GUI interface
- `pandas` — Data handling
- `demucs` — AI stem separation (requires PyTorch)
- `librosa` — Audio analysis fallback

Note: `basic-pitch` (TensorFlow-based MIDI transcription) requires TensorFlow, which is not yet available for Python 3.12 on Windows. The converter falls back to FFT-based pitch detection via `librosa`.

## Sharing Models

```bash
# Export your trained model
cp ~/.musicmp3/profile.json profile.json

# Import a model from the repo
cp profile.json ~/.musicmp3/profile.json
```

## License

GNU General Public License v3.0
