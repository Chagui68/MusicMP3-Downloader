# MusicMP3-Downloader

A Java CLI tool that downloads songs as MP3 and optionally converts them to Minecraft Note Block Studio (`.nbs`) format.

## Requirements

- Java 21+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (installed and on `PATH`)
- [FFmpeg](https://ffmpeg.org/) (installed and on `PATH`)

### For .nbs conversion

- `mp3-to-nbs` (recommended): `pip install git+https://github.com/devRaikou/mp3-to-nbs.git`
- Or `basic-pitch` for MIDI intermediate: `pip install basic-pitch`

## How it works

1. You enter a song name.
2. `yt-dlp` searches YouTube and downloads the best audio stream.
3. FFmpeg converts it to MP3 and saves it to `downloads/<SongName>.mp3`.
4. You're asked if you want to convert to `.nbs` format.
5. If yes, `mp3-to-nbs` analyzes the audio and generates a Note Block Studio file in `nbs_songs/<SongName>.nbs`.
   - Falls back to MP3 → WAV → MIDI via `basic-pitch` if `mp3-to-nbs` isn't installed.

## Build & Run

```sh
mvn package -q
java -jar target/MusicMP3-Downloader-1.0-SNAPSHOT.jar
```

## Project structure

```
downloads/       # MP3 files (kept after conversion)
nbs_songs/       # NBS files (for Minecraft Note Block Studio)
```

## Limitations

- Requires `yt-dlp` and `FFmpeg` to be installed separately.
- `.nbs` conversion requires `mp3-to-nbs` or `basic-pitch`.
- No search selection — always picks the first YouTube result.
