SEPARATION_AVAILABLE = False

try:
    from demucs import separate
    import torch
    import torchaudio

    SEPARATION_AVAILABLE = True
except ImportError:
    pass

from pathlib import Path

STEM_NAMES = ["bass", "drums", "vocals", "other"]


def separate_stems(input_path: str, output_dir: str) -> dict[str, str | None]:
    if not SEPARATION_AVAILABLE:
        print("[separator] demucs not installed — using original file as single stem")
        return {"other": input_path}

    print("[separator] Separating stems with Demucs (htdemucs)...")
    from demucs import separate

    try:
        separate.main([
            "-o", output_dir,
            str(input_path),
        ])
    except Exception as e:
        print(f"[separator] Demucs failed ({e}) — using original file")
        return {"other": input_path}

    base = Path(input_path).stem
    stem_dir = Path(output_dir) / "htdemucs" / base

    stems: dict[str, str | None] = {}
    for name in STEM_NAMES:
        stem_file = stem_dir / f"{name}.wav"
        if stem_file.exists():
            stems[name] = str(stem_file)
        else:
            stems[name] = None

    no_vocals = stem_dir / "no_vocals.wav"
    if no_vocals.exists() and not any(stems.values()):
        stems["other"] = str(no_vocals)
        stems["vocals"] = str(stem_dir / "vocals.wav") if (stem_dir / "vocals.wav").exists() else None

    if not any(stems.values()):
        stems["other"] = input_path

    return stems
