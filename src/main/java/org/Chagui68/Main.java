package org.Chagui68;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Scanner;

public class Main {

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        System.out.print("Enter song name: ");
        String query = scanner.nextLine().trim();
        if (query.isEmpty()) {
            System.err.println("No song name provided.");
            System.exit(1);
        }

        Path mp3File;
        try {
            mp3File = downloadMP3(query);
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            System.exit(1);
            return;
        }

        System.out.print("Convert to .nbs format? (y/n): ");
        String answer = scanner.nextLine().trim().toLowerCase();
        scanner.close();

        if (answer.equals("y") || answer.equals("yes")) {
            try {
                Path nbsFile = convertToNBS(mp3File);
            } catch (Exception e) {
                System.err.println("NBS conversion failed: " + e.getMessage());
                System.exit(1);
            }
        }
    }

    private static Path downloadMP3(String query) throws IOException, InterruptedException {
        Path downloadDir = Path.of("downloads");
        Files.createDirectories(downloadDir);

        String safeName = query.replaceAll("[\\\\/:*?\"<>|]", "_").replace(" ", "_");
        Path outputFile = downloadDir.resolve(safeName + ".mp3");

        System.out.println("Searching and downloading: " + query);

        ProcessBuilder pb = new ProcessBuilder(
                "yt-dlp",
                "-f", "bestaudio",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "-o", outputFile.toString(),
                "ytsearch1:" + query
        );

        pb.inheritIO();
        int exitCode = pb.start().waitFor();

        if (exitCode != 0) {
            throw new RuntimeException("Download failed with exit code " + exitCode);
        }

        System.out.println("Downloaded: " + outputFile.toAbsolutePath());
        return outputFile;
    }

    private static Path convertToNBS(Path mp3File) throws IOException, InterruptedException {
        Path nbsDir = Path.of("nbs_songs");
        Files.createDirectories(nbsDir);
        String songName = mp3File.getFileName().toString().replace(".mp3", "");
        Path nbsFile = nbsDir.resolve(songName + ".nbs");

        try {
            ProcessBuilder pb = new ProcessBuilder(
                    "mp3-to-nbs", mp3File.toString(), "-o", nbsFile.toString(), "--preset", "faithful"
            );
            pb.inheritIO();
            int exitCode = pb.start().waitFor();

            if (exitCode == 0 && Files.exists(nbsFile)) {
                System.out.println("Saved: " + nbsFile.toAbsolutePath());
                return nbsFile;
            }
        } catch (IOException e) {
            System.out.println("mp3-to-nbs not installed (" + e.getMessage() + ")");
        }

        System.out.println("Trying MIDI intermediate...");
        return convertViaMIDI(mp3File);
    }

    private static Path convertViaMIDI(Path mp3File) throws IOException, InterruptedException {
        Path nbsDir = Path.of("nbs_songs");
        String songName = mp3File.getFileName().toString().replace(".mp3", "");
        Path wavFile = mp3File.resolveSibling(songName + ".wav");
        Path midiFile = mp3File.resolveSibling(songName + ".mid");

        System.out.println("Decoding to WAV...");
        ProcessBuilder ffmpeg = new ProcessBuilder(
                "ffmpeg", "-y", "-i", mp3File.toString(), "-ac", "1", "-ar", "44100", wavFile.toString()
        );
        ffmpeg.inheritIO();
        int code = ffmpeg.start().waitFor();
        if (code != 0) throw new RuntimeException("FFmpeg decoding failed");
        System.out.println("WAV created: " + wavFile.toAbsolutePath());

        try {
            ProcessBuilder bp = new ProcessBuilder(
                    "basic-pitch", "midi", wavFile.toString(), midiFile.toString()
            );
            bp.inheritIO();
            int bpCode = bp.start().waitFor();

            if (bpCode == 0 && Files.exists(midiFile)) {
                System.out.println("MIDI created: " + midiFile.toAbsolutePath());
                System.out.println("Open the .mid in OpenNoteBlockStudio, then File -> Export as .nbs");
                Files.deleteIfExists(wavFile);
                return midiFile;
            }
        } catch (IOException e) {
            System.out.println("basic-pitch not installed (" + e.getMessage() + ")");
        }

        System.out.println("Could not auto-convert. To convert manually:");
        System.out.println("  1. Install basic-pitch: pip install basic-pitch");
        System.out.println("  2. Run: basic-pitch midi \"" + wavFile + "\" \"" + midiFile + "\"");
        System.out.println("  3. Open the .mid in OpenNoteBlockStudio (https://opennbs.org/)");
        System.out.println("  4. File -> Export -> .nbs");
        System.out.println();
        System.out.println("Or install mp3-to-nbs for direct conversion:");
        System.out.println("  pip install mp3-to-nbs");
        throw new RuntimeException("NBS conversion requires mp3-to-nbs or basic-pitch");
    }
}