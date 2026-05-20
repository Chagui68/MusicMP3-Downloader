import json
import math
import os
from pathlib import Path
from collections import Counter, defaultdict

import numpy as np
import soundfile as sf

from .nbs_playback import parse_nbs

SAMPLE_RATE = 44100

# ─── Audio feature extraction (reused from nbs_optimizer) ───

def _spectral_centroid(spec, freqs):
    total = np.sum(spec)
    if total < 1e-8: return 0.0
    return float(np.sum(freqs * spec) / total)


def _spectral_rolloff(spec, freqs, pct=0.85):
    cum = np.cumsum(spec)
    total = cum[-1]
    if total < 1e-8: return 0.0
    idx = np.searchsorted(cum, total * pct)
    return freqs[min(idx, len(freqs)-1)]


def extract_features_from_window(data, sr=SAMPLE_RATE):
    """Extract the 4 spectral features from audio window. Returns None if too short."""
    if len(data) < 64:
        return None
    n = min(len(data), 2048)
    windowed = data[:n] * np.hanning(n)
    if len(windowed) < 2048:
        windowed = np.pad(windowed, (0, 2048 - len(windowed)))
    fft = np.fft.rfft(windowed)
    mag = np.abs(fft)
    freqs = np.linspace(0, sr / 2, len(mag))

    centroid = _spectral_centroid(mag, freqs)
    rolloff = _spectral_rolloff(mag, freqs)

    envelope = np.abs(data)
    attack = float(np.max(envelope[:min(512, len(envelope)//2)])) / (float(np.mean(np.abs(data))) + 1e-8)

    half = len(data) // 2
    if half > 0:
        decay_ratio = float(np.sum(np.abs(data[half:])) / (np.sum(np.abs(data[:half])) + 1e-8))
    else:
        decay_ratio = 1.0

    return [centroid, rolloff, min(attack, 20), decay_ratio]


def extract_per_note_features(nbs_notes, audio_data, sr, tempo_bps=10):
    """For each note in NBS, extract the audio features at that time position.
    
    Returns list of (features, instrument) for each note that has valid audio.
    """
    if len(audio_data) == 0:
        print(f"[analyzer] WARNING: audio data is empty ({len(audio_data)} samples)")
        return []

    audio_len_sec = len(audio_data) / sr if sr > 0 else 0

    # Compute tick_seconds from NBS tempo
    tick_seconds = 1.0 / (tempo_bps * 2.0) if tempo_bps > 0 else 0.05
    max_tick = max((n["tick"] for n in nbs_notes), default=0)
    max_time = max_tick * tick_seconds

    # If the NBS tempo gives unrealistically large times, re-estimate from audio duration
    if max_time > audio_len_sec * 2 and max_tick > 0:
        old_tick_sec = tick_seconds
        tick_seconds = (audio_len_sec * 0.9) / max_tick
        print(f"[analyzer] WARNING: NBS tempo gives {max_time:.0f}s for {audio_len_sec:.0f}s audio. "
              f"Recalibrating tick_sec: {old_tick_sec:.4f} → {tick_seconds:.4f}")
    else:
        print(f"[analyzer] audio={audio_len_sec:.1f}s sr={sr} tempo={tempo_bps:.1f} "
              f"tick_sec={tick_seconds:.4f} max_tick={max_tick} max_time={max_time:.1f}s")

    results = []
    for note in nbs_notes:
        tick = note["tick"]
        start_time = tick * tick_seconds
        inst = note.get("instrument", 0)

        half = 0.06
        ws = max(0, int((start_time - half) * sr))
        we = min(len(audio_data), int((start_time + half) * sr))
        window = audio_data[ws:we]

        feats = extract_features_from_window(window, sr)
        if feats is None:
            continue
        results.append({
            "features": feats,
            "instrument": inst,
            "key": note.get("key", 0),
            "tick": tick,
        })
    print(f"[analyzer] Extracted features for {len(results)} / {len(nbs_notes)} notes")
    return results


# ─── NBS-only analysis (structural patterns) ───

def analyze_nbs_file(nbs_path: str) -> dict:
    """Extract patterns from a single NBS file."""
    data = parse_nbs(nbs_path)
    notes = data["notes"]
    if not notes:
        return {}

    name = data.get("song_name", Path(nbs_path).stem)
    tempo_bps = data.get("tempo_bps", 10)

    per_layer = defaultdict(list)
    per_instrument = defaultdict(list)
    for n in notes:
        inst = n.get("instrument", 0)
        layer = n.get("_layer_idx", 0)
        per_layer[layer].append(n)
        per_instrument[inst].append(n)

    inst_count = Counter()
    for n in notes:
        inst_count[n.get("instrument", 0)] += 1

    layer_insts = {}
    for layer, ns in sorted(per_layer.items()):
        insts = Counter(n.get("instrument", 0) for n in ns)
        layer_insts[layer] = insts.most_common(3)

    inst_keys = {}
    for inst, ns in per_instrument.items():
        keys = [n["key"] for n in ns]
        inst_keys[inst] = {
            "min": min(keys), "max": max(keys), "avg": sum(keys) / len(keys),
            "count": len(ns),
        }

    inst_velocities = {}
    for inst, ns in per_instrument.items():
        vels = [n.get("velocity", 100) for n in ns]
        inst_velocities[inst] = {
            "min": min(vels), "max": max(vels), "avg": sum(vels) / len(vels),
        }

    tick_counts = Counter(n["tick"] for n in notes)
    density = {
        "avg_notes_per_tick": sum(tick_counts.values()) / max(len(tick_counts), 1),
        "max_notes_per_tick": max(tick_counts.values()),
    }

    all_ticks = sorted(set(n["tick"] for n in notes))
    gaps = [all_ticks[i+1] - all_ticks[i] for i in range(len(all_ticks)-1)]

    return {
        "name": name,
        "total_notes": len(notes),
        "tempo_bps": tempo_bps,
        "duration_ticks": max((n["tick"] for n in notes), default=0),
        "num_layers": data.get("max_layer", 1),
        "tick_gap_avg": sum(gaps) / max(len(gaps), 1) if gaps else 0,
        "instrument_counts": dict(inst_count.most_common()),
        "instrument_keys": inst_keys,
        "instrument_velocities": inst_velocities,
        "layer_instruments": layer_insts,
        "note_density": density,
        "key_range": {
            "min": min(n["key"] for n in notes),
            "max": max(n["key"] for n in notes),
        },
    }


# ─── Learning from NBS + Audio pairs ───

def find_pairs(directory: str) -> list[tuple[str, str]]:
    """Find NBS+audio pairs in a directory. Returns [(nbs_path, audio_path), ...]."""
    d = Path(directory)
    pairs = []
    nbs_files = {}
    audio_files = {}
    
    # First pass: collect all NBS and audio files
    for f in d.iterdir():
        if f.suffix.lower() == ".nbs":
            nbs_files[f.stem] = str(f)
        elif f.suffix.lower() in [".mp3", ".wav", ".flac", ".m4a", ".ogg"]:
            audio_files[f.stem] = str(f)
    
    # Second pass: match pairs
    for stem, nbs_path in nbs_files.items():
        matched = False
        for ext in [".mp3", ".wav", ".flac", ".m4a", ".ogg"]:
            audio = d / f"{stem}{ext}"
            if audio.exists():
                pairs.append((nbs_path, str(audio)))
                matched = True
                break
        if not matched:
            print(f"[analyzer] WARNING: {stem}.nbs has no matching audio file")
    
    # Report unmatched audio files
    for stem in audio_files:
        if stem not in [Path(p[0]).stem for p in pairs]:
            print(f"[analyzer] WARNING: {stem} audio file has no matching .nbs")
    
    print(f"[analyzer] Found {len(pairs)} valid NBS+audio pairs out of {len(nbs_files)} NBS and {len(audio_files)} audio files")
    return sorted(pairs)


def learn_audio_model(nbs_dir: str) -> dict:
    """Scan a directory of NBS+audio pairs and learn a spectral→instrument model.

    For each note in each NBS, extracts audio features from the original audio
    and records what instrument the human arranger chose. Builds a statistical
    model (mean+std per feature per instrument) that can be used to predict
    the best instrument for new notes.
    """
    print(f"\n[analyzer] === Starting audio model training ===")
    print(f"[analyzer] Training directory: {nbs_dir}")
    
    # Debug: list all files in the training directory
    d = Path(nbs_dir)
    all_files = list(d.iterdir())
    nbs_count = sum(1 for f in all_files if f.suffix.lower() == ".nbs")
    audio_count = sum(1 for f in all_files if f.suffix.lower() in [".mp3", ".wav", ".flac", ".m4a", ".ogg"])
    print(f"[analyzer] Training dir '{nbs_dir}': {len(all_files)} total files, {nbs_count} NBS, {audio_count} audio")
    print("[analyzer] Files in directory:")
    for f in all_files:
        print(f"   - {f.name}")

    pairs = find_pairs(nbs_dir)
    if not pairs:
        print(f"[analyzer] No matching NBS+audio pairs found in {nbs_dir}")
        print(f"[analyzer] Each .nbs needs a matching .mp3/.wav/.flac with the same name (e.g. song.nbs + song.mp3)")
        return None

    print(f"[analyzer] Found {len(pairs)} NBS+audio pairs in {nbs_dir}")
    for nbs_path, audio_path in pairs[:5]:
        print(f"  {Path(nbs_path).name} + {Path(audio_path).name}")
    if len(pairs) > 5:
        print(f"  ... and {len(pairs)-5} more")

    # Collect training samples: for each instrument, a list of feature vectors
    training_data: dict[int, list[list[float]]] = defaultdict(list)
    per_song_stats = []
    total_notes_extracted = 0
    # Collect custom instrument definitions from all training files
    all_custom_instruments: dict[int, dict] = {}

    for nbs_path, audio_path in pairs:
        try:
            nbs_data = parse_nbs(nbs_path)
            notes = nbs_data.get("notes", [])
            if not notes:
                continue
            song_name = nbs_data.get("song_name", Path(nbs_path).stem)
            tempo_bps = nbs_data.get("tempo_bps", 10)
            # Merge custom instrument definitions
            for inst_id, idef in nbs_data.get("custom_instruments", {}).items():
                if inst_id not in all_custom_instruments:
                    all_custom_instruments[inst_id] = idef
        except Exception as e:
            print(f"  [skip] {Path(nbs_path).name}: parse error ({e})")
            continue

        # Load audio
        try:
            audio_data, sr = sf.read(audio_path)
            if audio_data.ndim > 1:
                audio_data = audio_data.mean(axis=1)
            if sr != SAMPLE_RATE:
                from scipy import signal
                ratio = SAMPLE_RATE / sr
                new_len = max(1, int(len(audio_data) * ratio))
                audio_data = signal.resample(audio_data, new_len).astype(np.float32)
                sr = SAMPLE_RATE
        except Exception as e:
            print(f"  [skip] {Path(audio_path).name}: load error ({e})")
            continue

        # Extract per-note features
        note_features = extract_per_note_features(notes, audio_data, sr, tempo_bps)
        if not note_features:
            print(f"  [skip] {song_name}: no valid features extracted")
            continue

        song_counts = Counter()
        for nf in note_features:
            inst = nf["instrument"]
            training_data[inst].append(nf["features"])
            song_counts[inst] += 1

        total_notes_extracted += len(note_features)
        top_insts = dict(song_counts.most_common(5))
        per_song_stats.append({
            "name": song_name,
            "notes_extracted": len(note_features),
            "instrument_distribution": top_insts,
        })
    print(f" ✓ {song_name:35s} {len(note_features):5d} notes "
        f"instruments: {list(top_insts.keys())}")
    print(f"   Source files: {nbs_path}, {audio_path}")

    if not training_data:
        print("[analyzer] No training data extracted from any pair")
        return None

    # Build statistical model per instrument
    feature_names = ["centroid", "rolloff", "attack", "decay"]
    instrument_model = {}
    for inst in sorted(training_data.keys()):
        vectors = np.array(training_data[inst])
        if len(vectors) < 2:
            continue
        mean = vectors.mean(axis=0).tolist()
        std = vectors.std(axis=0).tolist()
        # Normalize std: avoid zeros
        std = [max(s, 0.01) for s in std]
        instrument_model[str(inst)] = {
            "name": _inst_name(inst),
            "count": len(vectors),
            "mean": mean,
            "std": std,
        }

    # Also compute feature centroids per instrument for quick lookup
    feature_centroids = {}
    for inst, model in instrument_model.items():
        feature_centroids[inst] = model["mean"]

    print(f"\n[analyzer] Trained model on {total_notes_extracted} notes across {len(instrument_model)} instruments")
    for inst, m in sorted(instrument_model.items(), key=lambda x: -x[1]["count"]):
        print(f"  inst {int(inst):2d} ({m['name']:12s}): {m['count']:5d} samples  "
              f"mean=[{', '.join(f'{v:.0f}' for v in m['mean'])}]")

    # Build a simple nearest-centroid classifier function (serializable)
    # Also include raw samples (downsampled) for potentially better prediction
    model = {
        "type": "gaussian",
        "feature_names": feature_names,
        "instruments": instrument_model,
        "feature_centroids": feature_centroids,
    }

    # Build the per-note feature database for the frontend
    # Keep a sample of raw features for diagnostic/visualization
    feature_db = []
    for inst in sorted(training_data.keys()):
        vectors = training_data[inst]
        sample = vectors[:min(50, len(vectors))]
        for vec in sample:
            feature_db.append({
                "instrument": inst,
                "name": _inst_name(inst),
                "features": vec,
            })

    result = {
        "songs_analyzed": len(per_song_stats),
        "notes_extracted": total_notes_extracted,
        "model": model,
        "per_song": per_song_stats,
        "feature_samples": feature_db,
        "source_files": [Path(p[0]).name for p in pairs],
        "custom_instrument_defs": {str(k): v for k, v in all_custom_instruments.items()},
    }

    print(f"\n[analyzer] === Training complete ===")
    print(f"[analyzer] Songs processed: {len(per_song_stats)}")
    print(f"[analyzer] Total notes: {total_notes_extracted}")
    print(f"[analyzer] Instruments trained: {len(instrument_model)}")
    for song in per_song_stats:
        print(f"  - {song['name']}: {song['notes_extracted']} notes")

    return result


def predict_instrument(features: list[float], model: dict) -> int:
    """Predict the best instrument for given audio features using the learned model.
    Returns instrument 0-15 (standard NBS range).
    """
    instruments = model.get("instruments", {})
    if not instruments:
        return 0

    best_inst = 0
    best_score = -1e9

    for inst_str, profile in instruments.items():
        inst = int(inst_str)
        # Custom instruments (>=16) must have at least 3 samples to be considered
        if inst >= 16 and profile["count"] < 3:
            continue
        mean = np.array(profile["mean"])
        std = np.array(profile["std"])
        f = np.array(features[:4])

        # Gaussian log-likelihood (normalized)
        score = -np.sum(((f - mean) / std) ** 2)
        # Weight by sample count (more data = more confidence)
        count_weight = min(profile["count"] / 50, 1.0)
        score += math.log(count_weight + 0.1)

        if score > best_score:
            best_score = score
            best_inst = inst

    return best_inst


# ─── NBS-only profile (structural patterns) ───

def learn_profile(nbs_dir: str) -> dict:
    """Scan a directory of NBS files and learn a conversion profile.
    
    If audio files are found alongside NBS files, also trains an audio→instrument model.
    """
    nbs_dir = Path(nbs_dir)
    nbs_files = sorted(nbs_dir.glob("*.nbs"))
    if not nbs_files:
        print(f"[analyzer] No .nbs files found in {nbs_dir}")
        return {}

    print(f"[analyzer] Scanning {len(nbs_files)} NBS files in {nbs_dir}")
    reports = []
    for f in nbs_files:
        try:
            r = analyze_nbs_file(str(f))
            if r:
                reports.append(r)
                print(f"  {r['name'][:40]:40s} {r['total_notes']:5d} notes  "
                      f"keys={r['key_range']['min']}-{r['key_range']['max']}  "
                      f"layers={r['num_layers']}  top_insts={list(r['instrument_counts'].keys())[:4]}")
        except Exception as e:
            print(f"  {f.name}: skipped ({e})")

    if not reports:
        return {}

    # Aggregate patterns
    all_inst_counts = Counter()
    all_key_ranges = defaultdict(list)
    all_velocities = defaultdict(list)
    layer_role_patterns = defaultdict(lambda: defaultdict(int))

    for r in reports:
        for inst, count in r["instrument_counts"].items():
            all_inst_counts[inst] += count
        for inst, kr in r["instrument_keys"].items():
            all_key_ranges[inst].append((kr["min"], kr["max"], kr["avg"]))
        for inst, kv in r["instrument_velocities"].items():
            all_velocities[inst].append(kv["avg"])
        for layer, insts in r["layer_instruments"].items():
            for inst, _ in insts:
                layer_role_patterns[layer][inst] += 1

    # Build profile
    total_notes = sum(all_inst_counts.values())
    instrument_profile = {}
    for inst in range(16):
        if inst in all_inst_counts:
            pct = all_inst_counts[inst] / total_notes * 100
            krs = all_key_ranges.get(inst, [])
            if krs:
                min_k = min(k[0] for k in krs)
                max_k = max(k[1] for k in krs)
                avg_k = sum(k[2] for k in krs) / len(krs)
            else:
                min_k, max_k, avg_k = 0, 87, 33

            vels = all_velocities.get(inst, [80])
            avg_vel = sum(vels) / len(vels)

            instrument_profile[str(inst)] = {
                "name": _inst_name(inst),
                "usage_pct": round(pct, 2),
                "count": all_inst_counts[inst],
                "key_min": min_k, "key_max": max_k, "key_avg": round(avg_k, 1),
                "velocity_avg": round(avg_vel, 1),
            }

    # Derive role-based mapping from layer+instrument patterns
    layer_0_insts = Counter()
    layer_last_insts = Counter()
    layer_2_insts = Counter()

    for r in reports:
        layers = sorted(r["layer_instruments"].keys())
        if not layers:
            continue
        for inst, _ in r["layer_instruments"].get(0, []):
            layer_0_insts[inst] += 1
        if 2 in layers:
            for inst, _ in r["layer_instruments"].get(2, []):
                layer_2_insts[inst] += 1
        last = layers[-1]
        if last >= 2:
            for inst, _ in r["layer_instruments"].get(last, []):
                layer_last_insts[inst] += 1

    layer0_common = [i for i, _ in layer_0_insts.most_common(5)]
    highest_layer_common = [i for i, _ in layer_last_insts.most_common(5)]
    layer2_common = [i for i, _ in layer_2_insts.most_common(3)]

    role_scores = {
        "percussion": layer0_common if layer0_common else [1, 2, 3],
        "bass": layer2_common if layer2_common else [5, 0],
        "melody": highest_layer_common if highest_layer_common else [0, 8, 4],
    }

    def _first(insts):
        return [i for i in insts if i < 16][:1]

    melody_insts = role_scores.get("melody", [0, 8])
    percussion_insts = role_scores.get("percussion", [1, 2, 3])
    bass_insts = role_scores.get("bass", [5, 0])

    recommendation = {
        "stem_to_instrument": {
            "bass": _first(bass_insts) or [5],
            "drums": _first(percussion_insts) or [1],
            "percussion": _first(percussion_insts[:2]) or [2],
            "vocals": _first(melody_insts) or [8],
            "other": [i for i in melody_insts if i < 16][0:3] or [0],
            "guitar": _first(melody_insts[:2]) or [4],
            "piano": [0],
            "synth": _first(melody_insts[:2]) or [6],
            "pad": _first(melody_insts[:2]) or [7],
            "lead": _first(melody_insts) or [8],
        },
        "layer_assignments": {
            "bass": 2,
            "drums": 0,
            "melody": 3,
        },
        "key_range_target": {
            "min": min(r["key_range"]["min"] for r in reports),
            "max": max(r["key_range"]["max"] for r in reports),
        },
    }

    profile = {
        "songs_analyzed": len(reports),
        "total_notes_analyzed": total_notes,
        "instrument_usage": instrument_profile,
        "role_recommendations": role_scores,
        "recommended_mapping": recommendation,
        "source_files": [r["name"] for r in reports],
    }

    # Try to also train audio model if audio files are present
    audio_model = learn_audio_model(nbs_dir)
    if audio_model:
        profile["audio_model"] = audio_model

    return profile


def _inst_name(inst: int) -> str:
    names = ['Piano','BassDrum','Snare','Click','Guitar','Bass','Bell','Chime',
             'Flute','Xylophone','IronXylo','CowBell','Didgeridoo','Bit','Banjo','Pling']
    return names[inst] if inst < 16 else f"Custom{inst}"


def save_profile(profile: dict, output_path: str):
    import tempfile
    output_dir = os.path.dirname(output_path) or '.'
    fd, temp_path = tempfile.mkstemp(suffix='.json', dir=output_dir)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(profile, f, indent=2)
        os.replace(temp_path, output_path)
    except:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
    print(f"[analyzer] Profile saved to {output_path}")


def load_profile(profile_path: str) -> dict:
    with open(profile_path) as f:
        content = f.read()
        if not content.strip():
            return {}
        return json.loads(content)


def apply_profile_to_converter(
    profile: dict,
    stem_instrument_map: dict[str, int],
    instrument_map: dict[str, int],
) -> tuple[dict[str, int], dict[str, int]]:
    """Override converter's stem→instrument mapping using learned profile."""
    rec = profile.get("recommended_mapping", {})
    stem_map = rec.get("stem_to_instrument", {})

    out_stem = dict(stem_instrument_map)
    out_inst = dict(instrument_map)

    for stem, insts in stem_map.items():
        if insts and stem in out_stem:
            out_stem[stem] = insts[0]

    return out_stem, out_inst


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m musicmp3.nbs_analyzer <nbs_directory> [output_profile.json]")
        print()
        print("The directory should contain:")
        print("  .nbs files + corresponding .mp3/.wav/.flac files")
        print()
        print("Example layout:")
        print("  songs/")
        print("    Lonely_Day.nbs  +  Lonely_Day.mp3")
        print("    Mezmerizer.nbs  +  Mezmerizer.mp3")
        print("    Bohemian_Rhapsody.nbs  +  Bohemian_Rhapsody.mp3")
        print()
        print("The analyzer:")
        print("  1. Scans NBS structure (layers, instruments, key ranges)")
        print("  2. Aligns each NBS with its original audio")
        print("  3. Learns audio→instrument mapping from human-made arrangements")
        print("  4. Saves a profile to override converter instrument choices")
        print("  5. Converter then uses the model to pick better instruments per-note")
        sys.exit(1)

    nbs_dir = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "nbs_profile.json"

    profile = learn_profile(nbs_dir)
    if profile:
        save_profile(profile, output)
        print(f"\nProfile includes {profile['songs_analyzed']} songs, {profile['total_notes_analyzed']} notes")
        if "audio_model" in profile:
            m = profile["audio_model"]
            print(f"Audio model: {m['notes_extracted']} notes across {len(m['model']['instruments'])} instruments")
        print(f"Recommended mapping: {json.dumps(profile['recommended_mapping']['stem_to_instrument'], indent=2)}")
    else:
        print("No profile generated (no valid NBS files found)")
