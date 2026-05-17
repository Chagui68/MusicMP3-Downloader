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
        scanner.close();
        if (query.isEmpty()) {
            System.err.println("No song name provided.");
            System.exit(1);
        }

        try {
            downloadMP3(query);
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            System.exit(1);
        }
    }

    private static void downloadMP3(String query) throws IOException, InterruptedException {
        Path downloadDir = Path.of(System.getProperty("user.home"), "Music", "MusicMP3-Downloader");
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
    }
}