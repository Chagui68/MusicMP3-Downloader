import mido
from .nbs import midi_to_nbs_key, STEM_INSTRUMENT_MAP, INSTRUMENTS

TICKS_PER_SECOND = 10


def quantize_tick(seconds: float) -> int:
    return int(round(seconds * TICKS_PER_SECOND))


def compress_octave(nbs_key: int, target_low: int = 12, target_high: int = 72) -> int:
    if target_low <= nbs_key <= target_high:
        return nbs_key
    span = target_high - target_low + 1
    if nbs_key < target_low:
        diff = target_low - nbs_key
        shift = ((diff // span) + 1) * span
        return min(target_high, nbs_key + shift)
    diff = nbs_key - target_high
    shift = ((diff // span) + 1) * span
    return max(target_low, nbs_key - shift)


def midi_to_nbs(
    midi_path: str,
    stem_name: str = "other",
    instrument_override: int | None = None,
    target_low: int = 12,
    target_high: int = 72,
) -> list[dict]:
    mid = mido.MidiFile(midi_path)

    tempo = 500000
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                tempo = msg.tempo
                break
        else:
            continue
        break

    ticks_per_beat = mid.ticks_per_beat or 480

    inst = instrument_override
    if inst is None:
        mapped = STEM_INSTRUMENT_MAP.get(stem_name, "piano")
        inst = INSTRUMENTS.get(mapped, 0)

    notes_out: list[dict] = []
    for track in mid.tracks:
        abs_ticks = 0
        active: dict[int, int] = {}

        for msg in track:
            abs_ticks += msg.time

            if msg.type == "note_on" and msg.velocity > 0:
                active[msg.note] = abs_ticks
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                start_ticks = active.pop(msg.note, None)
                if start_ticks is not None:
                    dur_ticks = abs_ticks - start_ticks
                    if dur_ticks < 10:
                        continue
                    start_sec = mido.tick2second(start_ticks, ticks_per_beat, tempo)
                    nbs_key = compress_octave(midi_to_nbs_key(msg.note), target_low, target_high)
                    tick = quantize_tick(start_sec)
                    notes_out.append({
                        "tick": tick,
                        "layer": 0,
                        "key": nbs_key,
                        "instrument": inst,
                        "velocity": 100,
                        "panning": 100,
                        "pitch": -1,
                    })

        for note, start_ticks in active.items():
            start_sec = mido.tick2second(start_ticks, ticks_per_beat, tempo)
            nbs_key = compress_octave(midi_to_nbs_key(note), target_low, target_high)
            tick = quantize_tick(start_sec)
            notes_out.append({
                "tick": tick,
                "layer": 0,
                "key": nbs_key,
                "instrument": inst,
                "velocity": 100,
                "panning": 100,
                "pitch": -1,
            })

    return notes_out
