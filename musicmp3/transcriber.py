import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

TRANSCRIPTION_AVAILABLE = False
try:
    from basic_pitch.inference import predict_and_save, ICASSP_2022_MODEL_PATH
    TRANSCRIPTION_AVAILABLE = True
except ImportError:
    pass


def audio_to_midi(
    input_path: str,
    output_midi: str,
    onset_threshold: float = 0.3,
    frame_threshold: float = 0.3,
    minimum_note_length: int = 58,
    melodia_trick: bool = True,
    minimum_frequency: float = 80.0,
    maximum_frequency: float = 2000.0,
) -> str | None:
    if TRANSCRIPTION_AVAILABLE:
        print(f"[transcriber] basic-pitch (onset={onset_threshold} frame={frame_threshold} melodia={melodia_trick})")
        try:
            out_dir = str(Path(output_midi).parent)
            predict_and_save(
                audio_path_list=[input_path],
                output_directory=out_dir,
                save_midi=True,
                sonify_midi=False,
                save_model_outputs=False,
                save_notes=False,
                model_or_model_path=ICASSP_2022_MODEL_PATH,
                onset_threshold=onset_threshold,
                frame_threshold=frame_threshold,
                minimum_note_length=minimum_note_length,
                minimum_frequency=minimum_frequency,
                maximum_frequency=maximum_frequency,
                melodia_trick=melodia_trick,
            )
            midi_name = Path(input_path).stem + "_basic_pitch.mid"
            generated = Path(out_dir) / midi_name
            if generated.exists():
                generated.rename(output_midi)
                return output_midi
        except Exception as e:
            print(f"[transcriber] basic-pitch failed ({e})")

    return _transcribe_fft(input_path, output_midi)


def audio_to_midi_direct(
    input_path: str,
    output_midi: str,
    onset_threshold: float = 0.3,
    frame_threshold: float = 0.2,
    melodia_trick: bool = False,
) -> str | None:
    """Direct transcription without stem separation — often better for rich mixes."""
    return audio_to_midi(
        input_path, output_midi,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        melodia_trick=melodia_trick,
        minimum_frequency=65.0,
        maximum_frequency=2000.0,
    )


def _transcribe_fft(input_path: str, output_midi: str) -> str | None:
    print(f"[transcriber] Using FFT pitch detection for {Path(input_path).name}")
    try:
        import librosa
    except ImportError:
        print("[transcriber] librosa not available (pip install librosa)")
        return None

    try:
        y, sr = librosa.load(input_path, sr=22050, mono=True)
    except Exception as e:
        print(f"[transcriber] Failed to load audio: {e}")
        return None

    import mido
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    tempo_bpm = 120
    ticks_per_beat = mid.ticks_per_beat
    us_per_beat = 500000
    track.append(mido.MetaMessage("set_tempo", tempo=us_per_beat))
    track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4))

    hop_length = 512
    frame_duration = hop_length / sr

    fmin = 65
    fmax = 1047
    try:
        pitches, magnitudes = librosa.piptrack(
            y=y, sr=sr, fmin=fmin, fmax=fmax,
            hop_length=hop_length,
            threshold=0.15,
        )
    except Exception as e:
        print(f"[transcriber] Pitch detection failed: {e}")
        return None

    n_frames = pitches.shape[1]
    active_notes: dict[int, float] = {}
    midi_events: list[tuple[int, int, int, int]] = []

    for frame in range(n_frames):
        time_sec = frame * frame_duration
        index = magnitudes[:, frame].argmax()
        pitch = pitches[index, frame]
        mag = magnitudes[index, frame]

        if pitch > 0 and mag > 0.3:
            midi_note = int(round(12 * np.log2(pitch / 440.0) + 69))
            midi_note = max(0, min(127, midi_note))

            if midi_note in active_notes:
                continue

            active_notes[midi_note] = time_sec
        else:
            for note in list(active_notes.keys()):
                start = active_notes.pop(note)
                if time_sec - start < 0.05:
                    continue
                ticks_start = int(start * ticks_per_beat * (tempo_bpm / 60))
                ticks_end = int(time_sec * ticks_per_beat * (tempo_bpm / 60))
                duration = ticks_end - ticks_start
                if duration < 1:
                    continue
                midi_events.append((ticks_start, note, duration, int(mag * 100)))

    for note, start in list(active_notes.items()):
        time_sec = start
        ticks_start = int(time_sec * ticks_per_beat * (tempo_bpm / 60))
        midi_events.append((ticks_start, note, 120, 80))

    midi_events.sort(key=lambda x: x[0])

    current_tick = 0
    for tick, note, duration, vel in midi_events:
        delta = tick - current_tick
        if delta < 0:
            continue
        track.append(mido.Message("note_on", note=note, velocity=min(127, vel), time=delta))
        track.append(mido.Message("note_off", note=note, velocity=0, time=duration))
        current_tick = tick

    mid.save(output_midi)
    if Path(output_midi).exists():
        print(f"[transcriber] Saved MIDI ({len(midi_events)} notes)")
        return output_midi

    return None
