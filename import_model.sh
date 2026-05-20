#!/bin/bash
# Import trained model from repository

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_SRC="$SCRIPT_DIR/profile.json"
PROFILE_DST="$HOME/.musicmp3/profile.json"

echo "📥 Importar modelo desde repositorio"
echo "===================================="

if [ ! -f "$PROFILE_SRC" ]; then
    echo "❌ Error: No se encontró profile.json en el repositorio"
    echo "   Asegurate de que el repositorio incluya este archivo."
    exit 1
fi

# Create destination directory if needed
mkdir -p "$(dirname "$PROFILE_DST")"

# Copy profile.json
cp "$PROFILE_SRC" "$PROFILE_DST"

# Get stats
SONGS=$(python3 -c "import json; d=json.load(open('$PROFILE_DST')); print(d.get('songs_analyzed', 0))")
NOTES=$(python3 -c "import json; d=json.load(open('$PROFILE_DST')); print(d.get('total_notes_analyzed', 0))")
INSTR=$(python3 -c "import json; d=json.load(open('$PROFILE_DST')); print(len(d.get('instrument_usage', {})))")

echo "✅ Modelo importado: $PROFILE_DST"
echo "   - Canciones: $SONGS"
echo "   - Notas: $NOTES"
echo "   - Instrumentos: $INSTR"
echo ""
echo "🚀 Ahora podés iniciar el servidor:"
echo "   musicmp3-server"
