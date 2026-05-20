from pathlib import Path
import json
import math
import numpy as np
import soundfile as sf

from .nbs import write_nbs, INSTRUMENTS, STEM_INSTRUMENT_MAP
from .midi_to_nbs import midi_to_nbs
from .transcriber import audio_to_midi, audio_to_midi_direct
from .separator import separate_stems
from .nbs_playback import parse_nbs
from .nbs_analyzer import extract_per_note_features, predict_instrument

TARGET_LOW = 33
TARGET_HIGH = 80
TRANSPOSE = 0
TEMPO = 1000

_DEFAULT_PROFILE_PATH = None


def set_profile(profile_path: str | None):
    global _DEFAULT_PROFILE_PATH
    _DEFAULT_PROFILE_PATH = profile_path


def _load_profile_instrument_map() -> dict[str, int]:
    if not _DEFAULT_PROFILE_PATH:
        return STEM_INSTRUMENT_MAP
    try:
        with open(_DEFAULT_PROFILE_PATH) as f:
            profile = json.load(f)
        rec = profile.get("recommended_mapping", {})
        stem_map = rec.get("stem_to_instrument", {})
        override = dict(STEM_INSTRUMENT_MAP)
        for stem, insts in stem_map.items():
            if insts and stem in override:
                override[stem] = insts[0]
        return override
    except Exception:
        return STEM_INSTRUMENT_MAP


def _load_profile(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _refine_with_audio_model(
    nbs_path: str,
    audio_path: str,
    profile: dict,
    tempo_bps: float = 10,
) -> int:
    audio_model = profile.get("audio_model", None)
    if not audio_model or "model" not in audio_model:
        return 0

    model = audio_model["model"]
    if not model.get("instruments"):
        return 0

    audio_data, sr = sf.read(audio_path)
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)
    from scipy import signal
    if sr != 44100:
        ratio = 44100 / sr
        new_len = max(1, int(len(audio_data) * ratio))
        audio_data = signal.resample(audio_data, new_len).astype(np.float32)
        sr = 44100

    nbs_data = parse_nbs(nbs_path)
    notes = nbs_data.get("notes", [])
    if not notes:
        return 0

    note_features = extract_per_note_features(notes, audio_data, sr, tempo_bps)
    feat_by_tick: dict[int, dict] = {}
    for nf in note_features:
        feat_by_tick[nf["tick"]] = nf

    changed = 0
    refined = []
    for note in notes:
        tick = note["tick"]
        layer = note.get("_layer_idx", 0)
        nf = feat_by_tick.get(tick)
        if nf and nf["features"]:
            predicted = predict_instrument(nf["features"], model)
            if predicted != note.get("instrument", 0):
                changed += 1
            note["instrument"] = predicted
        refined.append(note)

    if changed == 0:
        return 0

    max_tick = max((n["tick"] for n in refined), default=0) + 1
    max_layer = nbs_data.get("max_layer", 1)
    tempo_raw = max(1, min(1000, int(tempo_bps * 100)))
    # Preserve original layers and custom instruments
    orig_layers = nbs_data.get("layers", [])
    layers = [
        orig_layers[i] if i < len(orig_layers) else {"name": f"Layer {i+1}", "volume": 100, "stereo": 100}
        for i in range(max_layer)
    ]
    custom_instruments = nbs_data.get("custom_instruments", {})

    from .nbs import _build_nbs_buf
    refined.sort(key=lambda x: (x["tick"], x.get("_layer_idx", x.get("layer", 0))))
    buf = _build_nbs_buf(max_tick, max_layer, tempo_raw, refined, layers, "", custom_instruments)
    with open(nbs_path, "wb") as f:
        f.write(buf)

    return changed


def convert_file(
    input_path: str,
    output_dir: str = "nbs_songs",
    target_low: int = TARGET_LOW,
    target_high: int = TARGET_HIGH,
    transpose: int = TRANSPOSE,
    profile_path: str | None = None,
    mode: str = "full",
) -> str | None:
    """Convert audio to NBS.
    
    mode: "full" (Demucs + basic-pitch), "direct" (basic-pitch no separation),
          "whiten" (basic-pitch with tweaked params), "fft" (librosa only)
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)
    song_name = Path(input_path).stem

    profile = None
    stem_map = STEM_INSTRUMENT_MAP

    if profile_path:
        try:
            profile = _load_profile(profile_path)
            rec = profile.get("recommended_mapping", {})
            stem_map_rec = rec.get("stem_to_instrument", {})
            stem_map = dict(STEM_INSTRUMENT_MAP)
            for stem, insts in stem_map_rec.items():
                if insts and stem in stem_map:
                    stem_map[stem] = insts[0]
            audio_model = profile.get("audio_model", None)
            if audio_model:
                print(f"[converter] Using audio model ({audio_model['notes_extracted']} trained notes)")
            print(f"[converter] Using profile: {profile.get('songs_analyzed', 0)} songs analyzed")
        except Exception as e:
            print(f"[converter] Failed to load profile: {e}")
    else:
        stem_map = _load_profile_instrument_map()

    if mode == "direct":
        print(f"[converter] Mode: DIRECT (no stem separation)")
        return _convert_direct(input_path, out_dir, song_name, stem_map,
                               target_low, target_high, transpose, profile)

    elif mode == "whiten":
        print(f"[converter] Mode: WHITEN (basic-pitch with tweaked params)")
        return _convert_stems(input_path, out_dir, song_name, stem_map,
                              target_low, target_high, transpose, profile,
                              onset_threshold=0.15, frame_threshold=0.15,
                              minimum_note_length=32, melodia_trick=False)

    elif mode == "fft":
        print(f"[converter] Mode: FFT (librosa only, no ML)")
        return _convert_direct(input_path, out_dir, song_name, stem_map,
                               target_low, target_high, transpose, profile,
                               use_fft=True)

    else:  # full
        print(f"[converter] Mode: FULL (Demucs + basic-pitch)")
        return _convert_stems(input_path, out_dir, song_name, stem_map,
                              target_low, target_high, transpose, profile)


def _convert_stems(
  input_path, out_dir, song_name, stem_map,
  target_low, target_high, transpose, profile,
  onset_threshold=0.3, frame_threshold=0.3,
  minimum_note_length=58, melodia_trick=True,
) -> str | None:
    """Convert using stem separation + per-stem transcription."""
    print(f"[converter] Separating stems...")
    
    audio_data, sr = sf.read(input_path)
    audio_duration = len(audio_data) / sr
    print(f"[converter] Audio duration: {audio_duration:.2f}s")
    
    stems = separate_stems(input_path, str(out_dir / "stems"))

    all_notes = []
    layers_info = []

    layer_index = 0
    for stem_name, stem_path in stems.items():
        if stem_path is None:
            continue

        print(f"[converter] Transcribing stem '{stem_name}'...")
        midi_path = str(out_dir / f"{song_name}_{stem_name}.mid")
        result = audio_to_midi(
            stem_path, midi_path,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=minimum_note_length,
            melodia_trick=melodia_trick,
        )

        if result is None or not Path(result).exists():
            print(f"[converter] Skipping stem '{stem_name}' (transcription failed)")
            continue

        inst = INSTRUMENTS.get(stem_map.get(stem_name, "piano"), 0)
        notes = midi_to_nbs(
            midi_path,
            stem_name=stem_name,
            instrument_override=inst,
            target_low=target_low,
            target_high=target_high,
            transpose=transpose,
        )

        for n in notes:
            n["layer"] = layer_index
            all_notes.append(n)

        layers_info.append({
            "name": stem_name.capitalize(),
            "volume": 100,
            "stereo": 100,
        })
        layer_index += 1

    nbs_path = str(out_dir / f"{song_name}.nbs")
    write_nbs(nbs_path, TEMPO, all_notes, layers_info, song_name=song_name, audio_duration=audio_duration)

    # Refine with audio model if available
    if profile and profile.get("audio_model"):
        if Path(input_path).exists():
            print(f"[converter] Refining instruments with audio model...")
            changed = _refine_with_audio_model(nbs_path, input_path, profile, TEMPO / 100.0)
            print(f"[converter] Refined {changed} notes using audio model")

    for stem_name in stems:
        midi_path = out_dir / f"{song_name}_{stem_name}.mid"
        if midi_path.exists():
            midi_path.unlink()

    print(f"[converter] Saved: {nbs_path}")
    return nbs_path


def _convert_direct(
  input_path, out_dir, song_name, stem_map,
  target_low, target_high, transpose, profile,
  use_fft=False,
) -> str | None:
    """Convert without stem separation — transcribe full audio directly."""
    print(f"[converter] Transcribing full audio {'(FFT)' if use_fft else '(basic-pitch direct)'}...")
    
    audio_data, sr = sf.read(input_path)
    audio_duration = len(audio_data) / sr
    print(f"[converter] Audio duration: {audio_duration:.2f}s")
    
    midi_path = str(out_dir / f"{song_name}.mid")

    if use_fft:
        from .transcriber import _transcribe_fft
        result = _transcribe_fft(input_path, midi_path)
    else:
        result = audio_to_midi_direct(input_path, midi_path)

    if result is None or not Path(result).exists():
        print(f"[converter] Transcription failed")
        return None

    inst = INSTRUMENTS.get("piano", 0)
    all_notes = midi_to_nbs(
        midi_path,
        stem_name="full",
        instrument_override=inst,
        target_low=target_low,
        target_high=target_high,
        transpose=transpose,
    )

    for n in all_notes:
        n["layer"] = 0

    layers_info = [{"name": "Full", "volume": 100, "stereo": 100}]
    nbs_path = str(out_dir / f"{song_name}.nbs")
    write_nbs(nbs_path, TEMPO, all_notes, layers_info, song_name=song_name, audio_duration=audio_duration)

    if profile and profile.get("audio_model"):
        if Path(input_path).exists():
            print(f"[converter] Refining instruments with audio model...")
            changed = _refine_with_audio_model(nbs_path, input_path, profile, TEMPO / 100.0)
            print(f"[converter] Refined {changed} notes using audio model")

    midi_p = Path(midi_path)
    if midi_p.exists():
        midi_p.unlink()

    print(f"[converter] Saved: {nbs_path}")
    return nbs_path
