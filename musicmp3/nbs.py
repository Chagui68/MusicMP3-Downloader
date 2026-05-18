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


def write_nbs(path: str, tempo: int, notes: list[dict], layers: list[dict]):
    if not notes:
        notes = []
    if not layers:
        layers = []

    max_tick = max((n["tick"] for n in notes), default=0) + 1
    max_layer = max((n["layer"] for n in notes), default=0) + 1

    temp_path = path + ".tmp"
    with open(temp_path, "wb") as f:
        f.write(struct.pack("<h", 0))
        f.write(struct.pack("<h", max_layer))
        _write_string(f, "")
        _write_string(f, "")
        _write_string(f, "")
        _write_string(f, "Converted by MusicMP3-Downloader 2.0")
        f.write(struct.pack("<h", max(1, min(999, tempo))))
        f.write(struct.pack("<b", 0))
        f.write(struct.pack("<b", 0))
        f.write(struct.pack("<b", 0))
        f.write(struct.pack("<i", 0))
        f.write(struct.pack("<i", 0))
        f.write(struct.pack("<i", 0))
        f.write(struct.pack("<i", 0))
        f.write(struct.pack("<i", 0))
        _write_string(f, "")
        f.write(struct.pack("<b", 0))
        f.write(struct.pack("<b", 0))
        f.write(struct.pack("<h", 0))

        notes_by_tick: dict[int, list[dict]] = {}
        for n in notes:
            notes_by_tick.setdefault(n["tick"], []).append(n)

        sorted_ticks = sorted(notes_by_tick.keys())
        current_tick = -1
        for tick in sorted_ticks:
            tick_jump = tick - current_tick
            f.write(struct.pack("<h", tick_jump))
            current_tick = tick

            layer_notes = notes_by_tick[tick]
            layer_notes.sort(key=lambda x: x["layer"])
            current_layer = -1
            for n in layer_notes:
                layer_jump = n["layer"] - current_layer
                f.write(struct.pack("<h", layer_jump))
                current_layer = n["layer"]
                f.write(struct.pack("<b", n["key"]))
                f.write(struct.pack("<b", n.get("instrument", 0)))
                f.write(struct.pack("<b", n.get("velocity", 100)))
                f.write(struct.pack("<b", n.get("panning", 100)))
                f.write(struct.pack("<h", n.get("pitch", -1)))

            f.write(struct.pack("<h", 0))

        f.write(struct.pack("<h", 0))

        for i in range(max_layer):
            layer = layers[i] if i < len(layers) else {}
            _write_string(f, layer.get("name", f"Layer {i + 1}"))
            f.write(struct.pack("<b", 0))
            f.write(struct.pack("<b", layer.get("volume", 100)))
            f.write(struct.pack("<b", layer.get("stereo", 100)))

    os.replace(temp_path, path)
