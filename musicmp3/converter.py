from pathlib import Path

from .nbs import write_nbs, INSTRUMENTS, STEM_INSTRUMENT_MAP
from .midi_to_nbs import midi_to_nbs
from .transcriber import audio_to_midi
from .separator import separate_stems

TARGET_LOW = 12
TARGET_HIGH = 72
TEMPO = 100


def convert_file(input_path: str, output_dir: str = "nbs_songs") -> str | None:
    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)
    song_name = Path(input_path).stem

    print(f"[converter] Separating stems...")
    stems = separate_stems(input_path, str(out_dir / "stems"))

    all_notes = []
    layers_info = []

    layer_index = 0
    for stem_name, stem_path in stems.items():
        if stem_path is None:
            continue

        print(f"[converter] Transcribing stem '{stem_name}'...")
        midi_path = str(out_dir / f"{song_name}_{stem_name}.mid")
        result = audio_to_midi(stem_path, midi_path)

        if result is None or not Path(result).exists():
            print(f"[converter] Skipping stem '{stem_name}' (transcription failed)")
            continue

        inst = INSTRUMENTS.get(STEM_INSTRUMENT_MAP.get(stem_name, "piano"), 0)
        notes = midi_to_nbs(
            midi_path,
            stem_name=stem_name,
            instrument_override=inst,
            target_low=TARGET_LOW,
            target_high=TARGET_HIGH,
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
    write_nbs(nbs_path, TEMPO, all_notes, layers_info)

    for stem_name in stems:
        midi_path = out_dir / f"{song_name}_{stem_name}.mid"
        if midi_path.exists():
            midi_path.unlink()

    print(f"[converter] Saved: {nbs_path}")
    return nbs_path
