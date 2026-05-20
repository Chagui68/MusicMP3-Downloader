#!/bin/bash
# Setup script to train the model with your own songs
# This downloads audio from YouTube and trains the model

set -e

echo "======================================"
echo " MusicMP3 Model Setup"
echo "======================================"

# Create training directory
TRAIN_DIR="$HOME/.musicmp3/training"
mkdir -p "$TRAIN_DIR"

# Check if NBSsongs repo is cloned
if [ ! -d "NBSsongs" ]; then
    echo "Cloning NBSsongs repository..."
    git clone https://github.com/nickg2/NBSsongs.git
fi

# List of songs to train with (name + YouTube search query)
SONGS=(
    "Bad Apple:Bad Apple!! Touhou piano"
    "Believer:Imagine Dragons Believer"
    "Bohemian Rhapsody:Queen Bohemian Rhapsody"
    "Pallet Town:Pokemon Pallet Town theme"
    "Axel F:Crazy Frog Axel F"
    "Take On Me:A-ha Take On Me"
    "Clocks:Coldplay Clocks"
    "Fireflies:Owl City Fireflies"
    "Still Alive:Portal Still Alive"
    "Moonlight Sonata:Beethoven Moonlight Sonata"
)

# Download and prepare training data
echo ""
echo "Downloading training data..."
for song in "${SONGS[@]}"; do
    NAME="${song%%:*}"
    QUERY="${song##*:}"
    
    NBS_FILE=$(find NBSsongs/songs -iname "*${NAME}*" -type f | head -1)
    
    if [ -n "$NBS_FILE" ] && [ -f "$NBS_FILE" ]; then
        echo "  Found: $(basename "$NBS_FILE")"
        cp "$NBS_FILE" "$TRAIN_DIR/"
        
        if [ ! -f "$TRAIN_DIR/$(basename "$NBS_FILE" .nbs).mp3" ]; then
            echo "  Downloading: $QUERY"
            yt-dlp -x --audio-format mp3 --audio-quality 128K \
                -o "$TRAIN_DIR/$(basename "$NBS_FILE" .nbs).%(ext)s" \
                "ytsearch1:$QUERY" 2>/dev/null || true
        fi
    fi
done

# Train the model
echo ""
echo "Training model..."
python3 train_with_real_audio.py

echo ""
echo "======================================"
echo " Setup complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Run: musicmp3-server"
echo "2. Open: http://127.0.0.1:8000"
echo "3. Go to: 🧠 Entrenar modelo"
echo ""
