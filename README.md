# MusicMP3-Downloader

A simple Java CLI tool that downloads songs as MP3 files by name.

## Requirements

- Java 21+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (installed and on `PATH`)
- [FFmpeg](https://ffmpeg.org/) (installed and on `PATH`)

## How it works

1. You enter a song name.
2. The program runs `yt-dlp ytsearch1:<query>` to find the best matching YouTube video.
3. `yt-dlp` downloads the best available audio stream (Opus or M4A).
4. `yt-dlp` pipes the audio through `FFmpeg` to convert it to MP3 with the highest quality (`-aq 0`).
5. The resulting MP3 is saved to `~/Music/MusicMP3-Downloader/<SongName>.mp3`.

The program is a thin Java wrapper around two mature external tools — it doesn't re-implement YouTube extraction or audio conversion. All the heavy lifting is done by `yt-dlp` and `FFmpeg`.

## Build & Run

```sh
mvn package -q
java -jar target/MusicMP3-Downloader-1.0-SNAPSHOT.jar
```

## Limitations

- Requires `yt-dlp` and `FFmpeg` to be installed separately.
- No search selection — always picks the first YouTube result.
- Downloaded audio is re-encoded, so quality depends on YouTube's source.
- Legality varies by jurisdiction; downloading copyrighted music may violate YouTube's ToS.
