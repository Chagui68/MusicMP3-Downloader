import os
from pathlib import Path

from musicmp3.downloader import download_song
from musicmp3.converter import convert_file
from musicmp3.separator import SEPARATION_AVAILABLE
from musicmp3.transcriber import TRANSCRIPTION_AVAILABLE

try:
    import gradio as gr
except ImportError:
    print("gradio not installed. Run: pip install gradio")
    raise


def process(query: str, file_path: str | None) -> str:
    if file_path:
        input_path = str(file_path)
    elif query and query.strip():
        try:
            input_path = str(download_song(query.strip()))
        except Exception as e:
            return f"Download failed: {e}"
    else:
        return "Enter a song name or upload a file."

    try:
        result = convert_file(input_path)
        if result:
            return f"Done! NBS file saved: {result}"
        return "Conversion failed — no stems could be transcribed."
    except Exception as e:
        return f"Conversion error: {e}"


def main():
    status = " | ".join([
        "yt-dlp: available",
        f"Demucs: {'✓' if SEPARATION_AVAILABLE else '✗ (pip install demucs torch)'}",
        f"basic-pitch: {'✓' if TRANSCRIPTION_AVAILABLE else '✗ (pip install basic-pitch)'}",
        "Built-in FFT: active",
    ])

    with gr.Blocks(title="MusicMP3 → NBS Converter") as app:
        gr.Markdown("# MusicMP3 → Minecraft Note Block Converter")
        gr.Markdown(f"**Status:** {status}")

        with gr.Row():
            query_input = gr.Textbox(label="Song name (YouTube)", placeholder="e.g. Never Gonna Give You Up", scale=3)
        with gr.Row():
            file_input = gr.File(label="Or upload an audio file", file_types=[".mp3", ".wav", ".flac", ".m4a", ".ogg"], scale=3)
        with gr.Row():
            btn = gr.Button("Convert", variant="primary")
        output = gr.Textbox(label="Result")

        btn.click(fn=process, inputs=[query_input, file_input], outputs=output)

    app.launch(share=False)


if __name__ == "__main__":
    main()
