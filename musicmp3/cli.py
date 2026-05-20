import argparse
import sys
from pathlib import Path

from .downloader import download_song
from .converter import convert_file


def main():
    parser = argparse.ArgumentParser(description="Convert songs to Minecraft Note Block (.nbs) format")
    parser.add_argument("query", nargs="?", help="Song name or YouTube URL")
    parser.add_argument("--file", "-f", help="Local audio file path")
    parser.add_argument("--output", "-o", default="nbs_songs", help="Output directory for .nbs files")
    parser.add_argument("--download-only", action="store_true", help="Only download, skip conversion")
    parser.add_argument("--low", type=int, default=33, help="Lowest NBS key (default: 33)")
    parser.add_argument("--high", type=int, default=80, help="Highest NBS key (default: 80)")
    parser.add_argument("--transpose", type=int, default=0, help="Semitones to transpose (default: 0)")

    args = parser.parse_args()

    if args.file:
        input_path = args.file
    elif args.query:
        print(f"[main] Downloading: {args.query}")
        input_path = str(download_song(args.query))
        print(f"[main] Downloaded: {input_path}")
    else:
        query = input("Song name / YouTube URL: ").strip()
        if not query:
            print("No input provided")
            sys.exit(1)
        print(f"[main] Downloading: {query}")
        input_path = str(download_song(query))
        print(f"[main] Downloaded: {input_path}")

    if args.download_only:
        print(f"[main] Download-only mode. File at: {input_path}")
        return

    result = convert_file(input_path, args.output, target_low=args.low, target_high=args.high, transpose=args.transpose)
    if result:
        print(f"\n Done! NBS file: {result}")
    else:
        print("\n Conversion failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
