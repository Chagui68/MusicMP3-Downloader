import os, sys, urllib.request, subprocess, tempfile, shutil, wave, struct
from pathlib import Path

SAMPLES_DIR = Path(__file__).parent / "samples"
SAMPLE_RATE = 44100

ASSET_CDN = "https://raw.githubusercontent.com/InventivetalentDev/minecraft-assets/1.21.4/assets/minecraft/sounds/note"

INSTRUMENT_NAMES = {
    0: "harp", 1: "bd", 2: "snare", 3: "hat", 4: "bassattack",
    5: "flute", 6: "bell", 7: "guitar", 8: "icechime", 9: "xylobone",
    10: "iron_xylophone", 11: "cow_bell", 12: "didgeridoo", 13: "bit",
    14: "banjo", 15: "pling",
}


def get_sample_path(instrument_id: int) -> Path | None:
    return SAMPLES_DIR / f"inst{instrument_id}.wav"


def _urlretrieve(url: str, path: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; MusicMP3)"})
    with urllib.request.urlopen(req, timeout=30) as src:
        with open(path, "wb") as dst:
            dst.write(src.read())


def download_samples(force: bool = False) -> bool:
    """Download Minecraft note block samples. Returns True if all 16 samples available."""
    if not force and all(get_sample_path(i).exists() for i in range(16)):
        return True

    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    all_ok = True
    for inst_id, name in INSTRUMENT_NAMES.items():
        out_path = get_sample_path(inst_id)
        if out_path.exists() and not force:
            continue

        url = f"{ASSET_CDN}/{name}.ogg"
        ogg_path = SAMPLES_DIR / f"{name}.ogg"
        try:
            print(f"[samples] Downloading {name}.ogg...")
            _urlretrieve(url, str(ogg_path))
            _convert_ogg_to_wav(str(ogg_path), str(out_path))
            ogg_path.unlink(missing_ok=True)
            print(f"[samples]  → {out_path.name} (ok)")
        except Exception as e:
            print(f"[samples] Failed {name}: {e}")
            if ogg_path.exists():
                ogg_path.unlink(missing_ok=True)
            all_ok = False

    if all_ok:
        return True

    print("[samples] Some downloads failed, generating fallback samples")
    _generate_fallback_samples()
    return all_ok


def _convert_ogg_to_wav(ogg_path: str, wav_path: str):
    """Convert OGG to WAV using pydub or ffmpeg."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_ogg(ogg_path)
        audio = audio.set_frame_rate(SAMPLE_RATE).set_channels(1)
        audio.export(wav_path, format="wav")
        return
    except ImportError:
        pass

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", ogg_path,
             "-ar", str(SAMPLE_RATE), "-ac", "1", wav_path],
            capture_output=True, timeout=30,
        )
    except Exception:
        raise RuntimeError("Cannot convert OGG — install ffmpeg or pydub")


def _generate_fallback_samples():
    import numpy as np

    for inst_id in range(16):
        out_path = get_sample_path(inst_id)
        if out_path.exists():
            continue

        # Generate a short tone at A4 (440Hz)
        dur = 0.5
        t = np.arange(int(SAMPLE_RATE * dur), dtype=np.float32) / SAMPLE_RATE
        freq = 440.0
        sig = np.sin(2 * np.pi * freq * t)
        env = np.exp(-t * 3.0)
        sig = (sig * env * 0.5 * 32767).astype(np.int16)

        with wave.open(str(out_path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(sig.tobytes())


if __name__ == "__main__":
    ok = download_samples(force="--force" in sys.argv)
    if ok:
        print(f"[samples] All 16 samples ready in {SAMPLES_DIR}")
    else:
        print(f"[samples] Some samples missing — using fallback")
