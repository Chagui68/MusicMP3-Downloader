import subprocess
from pathlib import Path


def download_song(query: str, output_dir: str = "downloads") -> Path:
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    safe = query.replace("/", "_").replace(" ", "_")
    safe = "".join(c for c in safe if c.isalnum() or c in "._-")
    output_path = out / f"{safe}.mp3"

    print(f"[download] Searching: {query}")
    subprocess.run(
        [
            "yt-dlp",
            "-f", "bestaudio",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", str(output_path),
            f"ytsearch1:{query}",
        ],
        check=True,
    )

    if not output_path.exists():
        mp3_files = list(out.glob("*.mp3"))
        if mp3_files:
            mp3_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return mp3_files[0]
        raise FileNotFoundError(f"No MP3 found for '{query}'")

    return output_path
