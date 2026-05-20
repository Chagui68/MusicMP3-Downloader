import os, tempfile
from pathlib import Path

import pandas as pd

from musicmp3.downloader import download_song
from musicmp3.converter import convert_file
from musicmp3.nbs import modify_nbs_file, _build_nbs_buf
from musicmp3.separator import SEPARATION_AVAILABLE
from musicmp3.transcriber import TRANSCRIPTION_AVAILABLE
from musicmp3.nbs_playback import render_nbs_to_wav, parse_nbs
from musicmp3.nbs_visualizer import generate_piano_roll

try:
    import gradio as gr
except ImportError:
    print("gradio not installed. Run: pip install gradio")
    raise

# ── lookup tables ──────────────────────────────────────────────────

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

INST_NAMES = {
    0: "Piano", 1: "BassDrum", 2: "Snare", 3: "Click",
    4: "Bass", 5: "Flute", 6: "Bell", 7: "Guitar",
    8: "Chime", 9: "Xylophone", 10: "IronXylo", 11: "CowBell",
    12: "Didgeridoo", 13: "Bit", 14: "Banjo", 15: "Pling",
}

INST_EMOJI = {
    0: "🟥", 1: "🟧", 2: "🟨", 3: "🟩",
    4: "🟦", 5: "🟪", 6: "🟫", 7: "⬛",
    8: "⬜", 9: "🔴", 10: "🟠", 11: "🟡",
    12: "🟢", 13: "🔵", 14: "🟣", 15: "🟤",
}

_INST_REV = {v: k for k, v in INST_NAMES.items()}

# ── helpers ─────────────────────────────────────────────────────────

def nbs_key_name(k: int) -> str:
    if k < 0 or k > 87:
        return str(k)
    midi = k + 21
    octave = midi // 12 - 1
    return f"{NOTE_NAMES[midi % 12]}{octave}"


def _parse_key(raw) -> int:
    if isinstance(raw, str):
        raw = raw.strip().split()[0]
    return int(raw)


def _parse_inst(raw) -> int:
    if isinstance(raw, str):
        raw = raw.strip()
        parts = raw.split()
        clean = " ".join(p for p in parts if not any(c in p for c in "🟥🟧🟨🟩🟦🟪🟫⬛⬜🔴🟠🟡🟢🔵🟣🟤"))
        if not clean:
            clean = parts[-1] if parts else "0"
        if clean in _INST_REV:
            return _INST_REV[clean]
        for name, idx in _INST_REV.items():
            if clean.lower() == name.lower():
                return idx
        parts2 = clean.split()
        return int(parts2[0]) if parts2 else 0
    return int(raw)


def _build_legend_html() -> str:
    items = "".join(
        f'<span style="display:inline-flex;align-items:center;margin:0 10px 4px 0;'
        f'font-size:13px;">'
        f'<span style="font-size:18px;margin-right:4px;">{INST_EMOJI[i]}</span>'
        f'{i} {INST_NAMES[i]}</span>'
        for i in range(16)
    )
    return f'<div style="line-height:2;">{items}</div>'


# ── core functions ─────────────────────────────────────────────────

def _render_previews(nbs_path: str):
    wav_path = os.path.join(tempfile.gettempdir(), f"preview_{Path(nbs_path).stem}.wav")
    try:
        render_nbs_to_wav(nbs_path, wav_path)
    except Exception:
        wav_path = None
    piano_roll_png = None
    try:
        pr_bytes = generate_piano_roll(nbs_path)
        if pr_bytes:
            import io
            from PIL import Image
            piano_roll_png = Image.open(io.BytesIO(pr_bytes))
    except Exception:
        pass
    return wav_path, piano_roll_png


def get_notes_table(nbs_path: str) -> pd.DataFrame | None:
    try:
        data = parse_nbs(nbs_path)
        rows = []
        for n in data["notes"]:
            kn = nbs_key_name(n["key"])
            rows.append({
                "Tick": n["tick"],
                "Note": f"{n['key']} {kn}",
                "Inst": n["instrument"],
                "Vel": n.get("velocity", 100),
                "Pan": n.get("panning", 100),
            })
        return pd.DataFrame(rows)
    except Exception:
        return None


def _df_to_notes(df: pd.DataFrame) -> list[dict]:
    notes = []
    for _, row in df.iterrows():
        notes.append({
            "tick": int(row["Tick"]),
            "layer": 0,
            "key": _parse_key(row["Note"]),
            "instrument": int(row["Inst"]),
            "velocity": int(row["Vel"]),
            "panning": int(row["Pan"]),
            "pitch": -1,
        })
    return notes


def _stats_md(df: pd.DataFrame, nbs_path: str) -> str:
    keys = df["Note"].apply(_parse_key)
    insts = df["Inst"]
    ticks = df["Tick"]
    try:
        data = parse_nbs(nbs_path)
        dur = max(n["start_time"] for n in data["notes"]) if data["notes"] else 0
    except Exception:
        dur = 0
    kmin = int(keys.min())
    kmax = int(keys.max())
    return (
        f"**{len(df)}** notes &nbsp;·&nbsp; "
        f"Keys **{nbs_key_name(kmin)}** ({kmin}) – **{nbs_key_name(kmax)}** ({kmax}) "
        f"&nbsp;·&nbsp; **{len(insts.unique())}** instruments "
        f"&nbsp;·&nbsp; **{dur:.1f}s** "
        f"&nbsp;·&nbsp; **{len(ticks.unique())}** ticks"
    )


def apply_table(nbs_path: str, df: pd.DataFrame | None, original_audio: str | None = None) -> tuple:
    if not nbs_path or df is None:
        return "No data", None, None, None, None, "", original_audio
    try:
        orig = parse_nbs(nbs_path)
    except Exception as e:
        return f"Error: {e}", None, None, None, None, "", original_audio

    max_layer = orig.get("max_layer", 1)
    song_name = orig.get("song_name", "")
    tempo_bps = orig.get("tempo_bps", 10)
    tempo_raw = max(1, min(999, int(tempo_bps * 100)))

    layers = [{"name": f"Layer {i+1}", "volume": 100, "stereo": 100}
              for i in range(max_layer)]

    notes = _df_to_notes(df)
    notes.sort(key=lambda x: (x["tick"], x["layer"]))
    max_tick = max((n["tick"] for n in notes), default=0) + 1

    buf = _build_nbs_buf(max_tick, max_layer, tempo_raw, notes, layers, song_name)
    out = os.path.join(tempfile.gettempdir(), f"edited_{Path(nbs_path).stem}.nbs")
    with open(out, "wb") as f:
        f.write(buf)

    wav_path, piano_roll_png = _render_previews(out)
    new_df = get_notes_table(out)
    stats = _stats_md(new_df, out) if new_df is not None else ""
    return f"Applied! {len(notes)} notes", wav_path, piano_roll_png, new_df, out, stats, original_audio


def process(query, file_path, target_low, target_high, transpose, transcription_mode="full"):
    is_nbs = False
    original_audio = None
    if file_path is not None:
        input_path = str(file_path)
        is_nbs = input_path.lower().endswith(".nbs")
        original_audio = input_path
    elif query and query.strip():
        try:
            input_path = str(download_song(query.strip()))
            original_audio = input_path
        except Exception:
            return "Download failed", None, None, None, None, "", None
    else:
        return "Enter a song name or upload a file.", None, None, None, None, "", None

    try:
        if is_nbs:
            out_name = Path(input_path).stem + "_modified.nbs"
            out_path = os.path.join(tempfile.gettempdir(), out_name)
            result = modify_nbs_file(input_path, out_path,
                                     target_low=target_low, target_high=target_high,
                                     transpose=transpose)
            msg_prefix = "NBS modified"
        else:
            result = convert_file(input_path,
                                  target_low=target_low, target_high=target_high,
                                  transpose=transpose,
                                  mode=transcription_mode)
            msg_prefix = f"Done ({transcription_mode})"

        if not result:
            return "Conversion failed", None, None, None, None, "", None

        wav_path, piano_roll_png = _render_previews(result)
        table_df = get_notes_table(result)
        stats = _stats_md(table_df, result) if table_df is not None else ""
        return f"{msg_prefix}! {Path(result).name}", wav_path, piano_roll_png, table_df, result, stats, original_audio
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error: {e}", None, None, None, None, "", None


# ── GUI ────────────────────────────────────────────────────────────

CSS = """
table.gradio-table { font-size: 13px; }
thead.gradio-table th { background: #2c3e50 !important; color: #fff !important; font-weight: 600; }
tbody tr:nth-child(even) { background: #f8f9fa; }
tbody tr:hover { background: #e8f4fd; }
td { white-space: nowrap; padding: 4px 8px !important; }
"""

def main():
    status = " · ".join([
        "yt-dlp ✓",
        f"Demucs {'✓' if SEPARATION_AVAILABLE else '✗'}",
        f"basic-pitch {'✓' if TRANSCRIPTION_AVAILABLE else '✗'}",
        "FFT ✓",
    ])

    with gr.Blocks(title="MusicMP3 → NBS Converter", theme=gr.themes.Soft(), css=CSS) as app:
        gr.Markdown("# 🎵 MusicMP3 → Minecraft Note Block Converter")
        gr.Markdown(f"`{status}`")

        current_nbs = gr.State(None)
        current_original = gr.State(None)

        with gr.Tabs():
            with gr.Tab("🎛 Convert"):
                with gr.Group():
                    with gr.Row(equal_height=True):
                        query_input = gr.Textbox(
                            label="YouTube song name",
                            placeholder="e.g. Never Gonna Give You Up",
                            scale=3,
                        )
                        file_input = gr.File(
                            label="Upload file",
                            file_types=[".mp3", ".wav", ".flac", ".m4a", ".ogg", ".nbs"],
                            scale=2,
                            type="filepath",
                        )
                with gr.Group():
                    gr.Markdown("### Transcription mode")
                    mode = gr.Radio(
                        choices=[
                            ("🎛 Full (Demucs + basic-pitch) — best quality, slow", "full"),
                            ("🎯 Direct (basic-pitch, no separation) — faster, less precise", "direct"),
                            ("🔧 Whiten (basic-pitch + aggressive params) — more notes, noisier", "whiten"),
                            ("📐 FFT (librosa only, no ML) — lightweight, low quality", "fft"),
                        ],
                        value="full",
                        label="",
                    )
                with gr.Group():
                    with gr.Row():
                        target_low = gr.Slider(0, 57, value=33, step=1, label="Low note")
                        target_high = gr.Slider(57, 90, value=80, step=1, label="High note")
                        transpose = gr.Slider(-24, 24, value=0, step=1, label="Transpose")
                btn = gr.Button("🎵 Convert & Preview", variant="primary", size="lg")
                output = gr.Textbox(label="Status")

            with gr.Tab("🎹 Note Editor"):
                editor_stats = gr.Markdown("*Convert a song first*")
                inst_legend = gr.HTML(_build_legend_html())

                editor_audio = gr.Audio(label="Audio preview", type="filepath", autoplay=False)
                editor_piano_roll = gr.Image(label="Piano roll", type="pil")

                with gr.Group():
                    gr.Markdown("### Quick edit (click a row below, then edit here)")
                    with gr.Row():
                        sel_tick = gr.Number(label="Tick", precision=0)
                        sel_key = gr.Number(label="Key", precision=0)
                        sel_inst = gr.Number(label="Inst (0-15)", precision=0, minimum=0, maximum=15)
                        sel_vel = gr.Number(label="Vel (0-100)", precision=0, minimum=0, maximum=100, value=100)
                        sel_pan = gr.Number(label="Pan (0-200)", precision=0, minimum=0, maximum=200, value=100)
                    with gr.Row():
                        save_row_btn = gr.Button("💾 Save row", variant="secondary", size="sm")
                        add_row_btn = gr.Button("➕ Add note", variant="secondary", size="sm")
                        delete_row_btn = gr.Button("🗑 Delete row", variant="secondary", size="sm")

                note_table = gr.Dataframe(
                    label="Double-click any cell to edit | Inst = number 0-15",
                    headers=["Tick", "Note", "Inst", "Vel", "Pan"],
                    interactive=True,
                    wrap=True,
                )

                apply_btn = gr.Button("✏️ Apply edits & update preview", variant="primary", size="lg")

                download_nbs = gr.File(label="⬇ Download NBS", visible=True)

            with gr.Tab("📥 Download original"):
                download_original = gr.File(label="⬇ Download original MP3", visible=True)

            with gr.Tab("🎵 NBS Player"):
                gr.Markdown("### Load any NBS file and play it back")
                player_file = gr.File(label="Upload .nbs file", file_types=[".nbs"], type="filepath")
                player_btn = gr.Button("▶ Play NBS", variant="primary", size="lg")
                player_status = gr.Textbox(label="Status")
                player_audio = gr.Audio(label="Playback", type="filepath", autoplay=True)
                player_piano_roll = gr.Image(label="Piano roll", type="pil")
                player_download = gr.File(label="⬇ Download WAV", visible=True)

        # ── event wiring ──

        # Convert → everything goes to Editor tab
        btn.click(
            fn=process,
            inputs=[query_input, file_input, target_low, target_high, transpose, mode],
            outputs=[output, editor_audio, editor_piano_roll, note_table, current_nbs, editor_stats, current_original],
        ).then(
            fn=lambda nbs, orig: (nbs, orig),
            inputs=[current_nbs, current_original],
            outputs=[download_nbs, download_original],
        )

        # Apply edits
        apply_btn.click(
            fn=apply_table,
            inputs=[current_nbs, note_table, current_original],
            outputs=[output, editor_audio, editor_piano_roll, note_table, current_nbs, editor_stats, current_original],
        ).then(
            fn=lambda nbs, orig: (nbs, orig),
            inputs=[current_nbs, current_original],
            outputs=[download_nbs, download_original],
        )

        # Play NBS (player tab)
        def play_nbs(nbs_path):
            if not nbs_path:
                return "Upload a .nbs file", None, None, None
            try:
                wav_path, piano_roll_png = _render_previews(nbs_path)
                if wav_path:
                    return f"OK — {Path(nbs_path).name}", wav_path, piano_roll_png, wav_path
                return "Render failed", None, None, None
            except Exception as e:
                return f"Error: {e}", None, None, None

        player_btn.click(
            fn=play_nbs,
            inputs=[player_file],
            outputs=[player_status, player_audio, player_piano_roll, player_download],
        )

        # Row selection → Quick edit panel
        def on_row_select(evt: gr.SelectData, table_df: pd.DataFrame | None):
            if table_df is None:
                return 0, 0, 0, 100, 100
            row_idx = evt.index[0]
            row = table_df.iloc[row_idx]
            return int(row["Tick"]), _parse_key(row["Note"]), int(row["Inst"]), int(row["Vel"]), int(row["Pan"])

        note_table.select(
            fn=on_row_select,
            inputs=[note_table],
            outputs=[sel_tick, sel_key, sel_inst, sel_vel, sel_pan],
        )

        # Save row
        def save_row(tick, key, inst, vel, pan, table_df: pd.DataFrame | None):
            if table_df is None:
                return table_df
            df = table_df.copy()
            kn = nbs_key_name(key)
            match = df.apply(
                lambda r: int(r["Tick"]) == tick and _parse_key(r["Note"]) == key and int(r["Inst"]) == inst,
                axis=1,
            )
            if match.any():
                idx = match.idxmax()
                df.at[idx, "Tick"] = tick
                df.at[idx, "Note"] = f"{key} {kn}"
                df.at[idx, "Inst"] = inst
                df.at[idx, "Vel"] = vel
                df.at[idx, "Pan"] = pan
            return df

        save_row_btn.click(
            fn=save_row,
            inputs=[sel_tick, sel_key, sel_inst, sel_vel, sel_pan, note_table],
            outputs=[note_table],
        )

        # Delete row
        def delete_row(tick, key, inst, table_df: pd.DataFrame | None):
            if table_df is None:
                return table_df
            df = table_df.copy()
            match = df.apply(
                lambda r: int(r["Tick"]) == tick and _parse_key(r["Note"]) == key and int(r["Inst"]) == inst,
                axis=1,
            )
            if match.any():
                df = df.drop(match.idxmax()).reset_index(drop=True)
            return df

        delete_row_btn.click(
            fn=delete_row,
            inputs=[sel_tick, sel_key, sel_inst, note_table],
            outputs=[note_table],
        )

        # Add row
        def add_row(table_df: pd.DataFrame | None):
            df = table_df.copy() if table_df is not None else pd.DataFrame(columns=["Tick", "Note", "Inst", "Vel", "Pan"])
            new_row = pd.DataFrame([{"Tick": 0, "Note": "33 F#3", "Inst": 0, "Vel": 100, "Pan": 100}])
            return pd.concat([df, new_row], ignore_index=True)

        add_row_btn.click(
            fn=add_row,
            inputs=[note_table],
            outputs=[note_table],
        )

    app.launch(share=False, inbrowser=True)


if __name__ == "__main__":
    main()
