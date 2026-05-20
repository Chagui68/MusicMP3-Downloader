import struct
import os

NBS_VERSION = 5

INSTRUMENTS = {
    "piano": 0,
    "bass_drum": 1,
    "snare": 2,
    "click": 3,
    "guitar": 4,
    "flute": 5,
    "bell": 6,
    "chime": 7,
    "xylophone": 8,
    "iron_xylophone": 9,
    "cow_bell": 10,
    "didgeridoo": 11,
    "bit": 12,
    "banjo": 13,
    "pling": 14,
}

STEM_INSTRUMENT_MAP: dict[str, str] = {
    "bass": "bass_drum",
    "drums": "click",
    "percussion": "snare",
    "vocals": "flute",
    "other": "piano",
    "guitar": "guitar",
    "piano": "piano",
    "synth": "bell",
    "pad": "chime",
    "lead": "flute",
}

MIDI_NBS_OFFSET = 33


def midi_to_nbs_key(midi_note: int) -> int:
    key = midi_note - MIDI_NBS_OFFSET
    return max(0, min(87, key))


def _write_string(f, s: str):
    data = s.encode("utf-8")
    f.write(struct.pack("<i", len(data)))
    f.write(data)


def _layer(n):
    return n.get("layer", n.get("_layer_idx", 0))


def _build_nbs_buf(max_tick: int, max_layer: int, tempo: int, notes: list[dict], layers: list[dict], song_name: str, custom_instruments: dict[int, dict] | None = None) -> bytearray:
    if not notes:
        notes = []
    if not layers:
        layers = []
    if custom_instruments is None:
        custom_instruments = {}

    # Build instrument ID remapping: original >15 → sequential 16,17,...
    sorted_custom = sorted(
        [(inst_id, idef) for inst_id, idef in custom_instruments.items() if inst_id >= 16],
        key=lambda x: x[0]
    )
    remap: dict[int, int] = {}
    for idx, (orig_id, _) in enumerate(sorted_custom):
        remap[orig_id] = 16 + idx

    buf = bytearray()

    def wb(v):
        buf.extend(struct.pack("<b", v))

    def wh(v):
        buf.extend(struct.pack("<h", max(-32768, min(32767, v))))

    def wi(v):
        buf.extend(struct.pack("<i", v))

    def ws(s):
        encoded = s.encode("utf-8") if s else b""
        wi(len(encoded))
        buf.extend(encoded)

    if max_tick <= 0:
        max_tick = max((n["tick"] for n in notes), default=0) + 1
    if max_layer <= 0:
        max_layer = max((_layer(n) for n in notes), default=0) + 1

    wh(0)
    wb(NBS_VERSION)
    wb(0)
    wh(max_tick)
    wh(max_layer)
    ws(song_name)
    ws("")
    ws("")
    ws("Converted by MusicMP3-Downloader 2.0")
    wh(max(1, min(1000, tempo)))
    wb(0); wb(0); wb(0)
    wi(0); wi(0); wi(0); wi(0); wi(0)
    ws("")
    wb(0); wb(0); wh(0)

    notes_by_tick: dict[int, list[dict]] = {}
    for n in notes:
        notes_by_tick.setdefault(n["tick"], []).append(n)

    sorted_ticks = sorted(notes_by_tick.keys())
    st_len = len(sorted_ticks)
    if st_len > 5:
        print(f"[nbs] sorted_ticks: first={sorted_ticks[:5]}, last={sorted_ticks[-5:]}, max={sorted_ticks[-1]}, len={st_len}")
        big_gaps = [(i, sorted_ticks[i]-sorted_ticks[i-1]) for i in range(1, st_len) if sorted_ticks[i]-sorted_ticks[i-1] > 1000]
        if big_gaps:
            print(f"[nbs] BIG GAPS: {big_gaps[:10]}")
    current_tick = -1
    for idx, tick in enumerate(sorted_ticks):
        tick_jump = tick - current_tick
        wh(tick_jump)
        current_tick = tick
        if idx < 10 or (tick_jump > 100 and idx > 3):
            print(f"[nbs write] idx={idx}, tick={tick}, jump={tick_jump}")

        layer_notes = notes_by_tick[tick]
        layer_notes.sort(key=lambda x: (_layer(x), x.get("key", 0)))
        current_layer = -1
        for n in layer_notes:
            nl = _layer(n)
            if nl <= current_layer:
                nl = current_layer + 1
            wh(nl - current_layer)
            current_layer = nl
            raw_inst = n.get("instrument", 0)
            mapped_inst = remap.get(raw_inst, raw_inst)
            wb(mapped_inst)
            wb(n.get("key", 0))
            wb(n.get("velocity", 100))
            wb(n.get("panning", 100))
            wh(n.get("pitch", -1))

        wh(0)

    wh(0)

    for i in range(max_layer):
        layer = layers[i] if i < len(layers) else {}
        ws(layer.get("name", f"Layer {i + 1}"))
        wb(0)
        wb(layer.get("volume", 100))
        wb(layer.get("stereo", 100))

    # Custom instrument section
    wb(min(len(sorted_custom), 240))
    for orig_id, idef in sorted_custom:
        ws(idef.get("name", f"Custom{orig_id}"))
        ws(idef.get("sound_file", f"custom_{orig_id}.ogg"))
        wb(idef.get("key", 45))
        wb(0)

    return buf


def write_nbs(path: str, tempo: int, notes: list[dict], layers: list[dict], song_name: str = "", custom_instruments: dict[int, dict] | None = None, audio_duration: float | None = None):
    if not notes:
        notes = []
    if not layers:
        layers = []

    max_tick_from_notes = max((n["tick"] for n in notes), default=0) + 1
    
    if audio_duration is not None:
        max_tick_from_audio = int(audio_duration * 10)
        max_tick = max(max_tick_from_notes, max_tick_from_audio)
        print(f"[nbs] Audio duration: {audio_duration:.2f}s, max_tick: {max_tick} (notes: {max_tick_from_notes}, audio: {max_tick_from_audio})")
    else:
        max_tick = max_tick_from_notes
    
    max_layer = max((_layer(n) for n in notes), default=0) + 1

    buf = _build_nbs_buf(max_tick, max_layer, tempo, notes, layers, song_name, custom_instruments)

    with open(path, "wb") as f:
        f.write(buf)


def modify_nbs_file(input_path: str, output_path: str, target_low: int = 33, target_high: int = 80, transpose: int = 0) -> str:
    from .nbs_playback import parse_nbs
    data = parse_nbs(input_path)

    notes = data["notes"]
    orig_layers = data.get("layers", [])
    max_layer = data.get("max_layer", 1)
    layers = []
    for i in range(max_layer):
        ol = orig_layers[i] if i < len(orig_layers) else {}
        layers.append({"name": ol.get("name", f"Layer {i+1}"), "volume": ol.get("volume", 100), "stereo": ol.get("stereo", 100)})

    # Preserve custom instruments from original NBS
    custom_instruments = data.get("custom_instruments", {})

    modified = []
    for n in notes:
        new_key = n["key"] + transpose
        if new_key < target_low:
            diff = target_low - new_key
            span = target_high - target_low + 1
            shift = ((diff // span) + 1) * span
            new_key = min(target_high, new_key + shift)
        elif new_key > target_high:
            diff = new_key - target_high
            span = target_high - target_low + 1
            shift = ((diff // span) + 1) * span
            new_key = max(target_low, new_key - shift)
        new_key = max(0, min(87, new_key))

        modified.append({
            "tick": n["tick"],
            "layer": n.get("_layer_idx", 0),
            "key": new_key,
            "instrument": n.get("instrument", 0),
            "velocity": n.get("velocity", 100),
            "panning": n.get("panning", 100),
            "pitch": n.get("pitch", -1),
        })

    max_tick_val = max((n["tick"] for n in modified), default=0) + 1
    tempo_raw = int(data.get("tempo_bps", 10) * 100)
    song_name = data.get("song_name", "")

    buf = _build_nbs_buf(
        max_tick=max_tick_val,
        max_layer=max_layer,
        tempo=tempo_raw,
        notes=modified,
        layers=layers,
        song_name=song_name,
        custom_instruments=custom_instruments,
    )

    with open(output_path, "wb") as f:
        f.write(buf)

    print(f"[modify_nbs] Done: {output_path} ({len(modified)} notes, transpose={transpose}, range=[{target_low}-{target_high}])")
    return output_path
