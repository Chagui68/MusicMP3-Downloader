import struct
import wave
import numpy as np
from pathlib import Path
from .sample_loader import get_sample_path, download_samples, SAMPLE_RATE

INSTRUMENT_NAMES = {
    0: "Piano", 1: "Bass Drum", 2: "Snare", 3: "Click",
    4: "Guitar", 5: "Bass", 6: "Bell", 7: "Chime",
    8: "Flute", 9: "Xylophone", 10: "Iron Xylophone",
    11: "Cow Bell", 12: "Didgeridoo", 13: "Bit",
    14: "Banjo", 15: "Pling",
}

def _read_short(data, offset):
    return struct.unpack_from("<h", data, offset)[0], offset + 2

def _read_byte(data, offset):
    return data[offset], offset + 1

def _read_int(data, offset):
    if offset + 4 > len(data):
        return 0, len(data)
    return struct.unpack_from("<i", data, offset)[0], offset + 4

def _read_string(data, offset):
    length, offset = _read_int(data, offset)
    if length <= 0 or length > len(data) - offset:
        return "", offset
    return data[offset:offset+length].decode("utf-8", errors="replace"), offset + length

def parse_nbs(path: str) -> dict:
    with open(path, "rb") as f:
        raw = f.read()
    o = 0
    first, o = _read_short(raw, o)
    version = 0
    if first == 0:
        version, o = _read_byte(raw, o)
        _, o = _read_byte(raw, o)
    if version >= 3 or first != 0:
        if first == 0:
            song_length, o = _read_short(raw, o)
        else:
            song_length = first
    else:
        song_length = 0
    max_layer, o = _read_short(raw, o)
    song_name, o = _read_string(raw, o)
    author, o = _read_string(raw, o)
    _, o = _read_string(raw, o)
    desc, o = _read_string(raw, o)
    tempo_raw, o = _read_short(raw, o)
    tempo_bps = tempo_raw / 100.0
    o += 3
    for _ in range(5):
        _, o = _read_int(raw, o)
    _, o = _read_string(raw, o)
    o += 1 + 1 + 2
    tick_seconds = 1.0 / (tempo_bps * 2.0)
    notes = []
    current_tick = -1
    while o < len(raw):
        tick_jump, o = _read_short(raw, o)
        if tick_jump <= 0:
            break
        current_tick += tick_jump
        current_layer = -1
        while o < len(raw):
            layer_jump, o = _read_short(raw, o)
            if layer_jump <= 0:
                break
            current_layer += layer_jump
            instrument, o = _read_byte(raw, o)
            key, o = _read_byte(raw, o)
            if version >= 4:
                velocity, o = _read_byte(raw, o)
                panning, o = _read_byte(raw, o)
                pitch, o = _read_short(raw, o)
            else:
                velocity = 100
                panning = 100
                pitch = -1
            notes.append({
                "tick": current_tick,
                "instrument": instrument,
                "key": key,
                "velocity": velocity,
                "panning": panning,
                "_layer_idx": current_layer,
                "start_time": current_tick * tick_seconds,
            })

    # Normalizar ticks: eliminar silencio inicial
    if notes:
        min_tick = min(n["tick"] for n in notes)
        if min_tick > 0:
            for n in notes:
                n["tick"] -= min_tick
                n["start_time"] = n["tick"] * tick_seconds
            print(f"[nbs] Normalizado: -{min_tick} ticks ({min_tick * tick_seconds:.1f}s)")

    # Leer layers
    layers = []
    for i in range(max_layer):
        if o >= len(raw):
            break
        lname, o = _read_string(raw, o)
        if o + 3 > len(raw):
            layers.append({"name": lname, "volume": 100, "stereo": 100})
            break
        o += 1
        lvolume = raw[o]
        o += 1
        lstereo = raw[o]
        o += 1
        layers.append({"name": lname, "volume": lvolume, "stereo": lstereo})

    # Leer custom instruments
    custom_instruments = {}
    if o < len(raw):
        inst_count = raw[o] & 0xFF
        o += 1
        for _ in range(inst_count):
            if o >= len(raw):
                break
            iname, o = _read_string(raw, o)
            sfile, o = _read_string(raw, o)
            if o >= len(raw):
                break
            skey = raw[o] & 0xFF
            o += 1
            if o >= len(raw):
                break
            o += 1
            custom_instruments[16 + len(custom_instruments)] = {
                "name": iname,
                "sound_file": sfile,
                "key": skey,
            }

    return {
        "notes": notes,
        "tempo_bps": tempo_bps,
        "tick_seconds": tick_seconds,
        "song_name": song_name,
        "max_layer": max_layer,
        "song_length": song_length,
        "layers": layers,
        "custom_instruments": custom_instruments,
    }

# Loaded sample cache: {instrument_id: numpy_array(float32)}
_sample_cache: dict[int, np.ndarray] = {}

def _load_samples():
    if _sample_cache:
        return
    download_samples()
    for inst_id in range(16):
        path = get_sample_path(inst_id)
        if path and path.exists():
            try:
                with wave.open(str(path), "rb") as wf:
                    sw = wf.getsampwidth()
                    frames = wf.getnframes()
                    raw = wf.readframes(frames)
                if sw == 2:
                    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
                elif sw == 4:
                    # Could be 32-bit int or float; try int32 first
                    data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483647.0
                elif sw == 1:
                    data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 255.0 * 2.0 - 1.0
                else:
                    data = np.frombuffer(raw, dtype=np.float32)
                _sample_cache[inst_id] = data.astype(np.float32)
            except Exception as e:
                print(f"[playback] Failed to load sample {inst_id}: {e}")

def _resample(data: np.ndarray, ratio: float) -> np.ndarray:
    if abs(ratio - 1.0) < 0.001:
        return data
    in_len = len(data)
    out_len = max(1, int(in_len / ratio))
    out_indices = np.linspace(0, in_len - 1, out_len)
    in_indices = np.arange(in_len)
    return np.interp(out_indices, in_indices, data).astype(np.float32)

def render_instrument_real(nbs_key: int, instrument: int, velocity: int, sample_rate: int) -> np.ndarray:
    _load_samples()
    base_data = _sample_cache.get(instrument)
    if base_data is None or len(base_data) < 100:
        return _render_synthetic(nbs_key, instrument, velocity, sample_rate)

    pitch_ratio = 2.0 ** ((nbs_key - 45) / 12.0)
    resampled = _resample(base_data, pitch_ratio)
    amp = velocity / 100.0
    fade_len = min(512, len(resampled))
    if fade_len > 0:
        resampled[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)
    return (resampled * amp).astype(np.float32)

def _render_synthetic(nbs_key: int, instrument: int, velocity: int, sample_rate: int) -> np.ndarray:
    freq = 440.0 * (2.0 ** ((nbs_key - 45) / 12.0))
    dur = 0.4
    n_samples = int(dur * sample_rate)
    t = np.arange(n_samples, dtype=np.float32) / sample_rate
    amp = velocity / 100.0

    if instrument == 0:
        sig = np.sin(2 * np.pi * freq * t) * 0.5
        sig += np.sin(2 * np.pi * freq * 2 * t) * 0.15
        sig += np.sin(2 * np.pi * freq * 3 * t) * 0.05
        env = np.exp(-t * 3.0)
    elif instrument == 1:
        sig = np.sin(2 * np.pi * freq * t) * 0.8
        sig += np.random.randn(n_samples) * 0.1 * np.exp(-t * 15.0)
        env = np.exp(-t * 8.0)
    elif instrument == 2:
        sig = np.random.randn(n_samples) * 0.4
        sig += np.sin(2 * np.pi * freq * t) * 0.3
        env = np.exp(-t * 10.0)
    elif instrument == 3:
        sig = np.random.randn(n_samples) * 0.6
        env = np.exp(-t * 40.0)
    else:
        sig = np.sin(2 * np.pi * freq * t) * 0.4
        sig += np.sin(2 * np.pi * freq * 2 * t) * 0.2
        sig += np.sin(2 * np.pi * freq * 4 * t) * 0.1
        env = np.exp(-t * 2.0)

    sig *= amp * env
    return sig.astype(np.float32)


def render_nbs_to_wav(nbs_path: str, output_path: str, sample_rate: int = SAMPLE_RATE) -> str:
    data = parse_nbs(nbs_path)
    notes = data["notes"]
    if not notes:
        print("[playback] No notes to render")
        return ""

    max_time = max(n["start_time"] for n in notes) + 2.0
    total_samples = int(max_time * sample_rate) + sample_rate

    print(f"[playback] Mixing {len(notes)} notes, {max_time:.1f}s")
    mix = np.zeros(total_samples, dtype=np.float32)

    last_pct = -1
    for i, note in enumerate(notes):
        start_sample = int(note["start_time"] * sample_rate)
        wav_data = render_instrument_real(note["key"], note["instrument"], note["velocity"], sample_rate)
        end = min(start_sample + len(wav_data), total_samples)
        if end > start_sample:
            mix[start_sample:end] += wav_data[:end - start_sample]

        pct = (i * 100) // len(notes)
        if pct > last_pct and pct % 10 == 0:
            print(f"[playback] {pct}%")
            last_pct = pct

    peak = np.max(np.abs(mix))
    if peak > 0:
        mix = mix / peak * 0.9

    mix_int = (mix * 32767).astype(np.int16)
    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(mix_int.tobytes())

    print(f"[playback] Saved: {output_path}")
    return output_path
