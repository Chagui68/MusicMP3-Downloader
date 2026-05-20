#!/bin/bash
# Export trained model to repository for sharing

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_SRC="$HOME/.musicmp3/profile.json"
PROFILE_DST="$SCRIPT_DIR/profile.json"

echo "📦 Exportar modelo entrenado"
echo "============================"

if [ ! -f "$PROFILE_SRC" ]; then
    echo "❌ Error: No se encontró profile.json en $PROFILE_SRC"
    echo "   Primero debés entrenar el modelo con:"
    echo "   python3 train_with_real_audio.py"
    exit 1
fi

# Copy profile.json
cp "$PROFILE_SRC" "$PROFILE_DST"

# Get stats
SONGS=$(python3 -c "import json; d=json.load(open('$PROFILE_DST')); print(d.get('songs_analyzed', 0))")
NOTES=$(python3 -c "import json; d=json.load(open('$PROFILE_DST')); print(d.get('total_notes_analyzed', 0))")
INSTR=$(python3 -c "import json; d=json.load(open('$PROFILE_DST')); print(len(d.get('instrument_usage', {})))")

echo "✅ Modelo exportado: $PROFILE_DST"
echo "   - Canciones: $SONGS"
echo "   - Notas: $NOTES"
echo "   - Instrumentos: $INSTR"
echo ""
echo "📝 Para compartir en GitHub:"
echo "   git add profile.json"
echo "   git commit -m \"Update model: $SONGS songs, $NOTES notes\""
echo "   git push"
