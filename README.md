# 🎵 MusicMP3 → Minecraft Note Block Converter

Convierte canciones de audio a archivos `.nbs` editables para Minecraft Note Block Studio, con un modelo de IA entrenable que aprende de tus conversiones.

## ✨ Características

- 🎹 **Conversión automática** de MP3/WAV/FLAC a NBS
- 🧠 **Modelo de IA entrenable** que mejora con cada canción
- 🎼 **Múltiples instrumentos** (Piano, Bass, Snare, Guitar, etc.)
- 📊 **Piano roll interactivo** con línea de reproducción sincronizada
- 🎯 **Optimización inteligente** de notas
- 🌐 **Interfaz web moderna** y fácil de usar
- 📥 **Descarga automática** desde YouTube
- 🎨 **Edición en tiempo real** de notas

## 🚀 Instalación Rápida

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/musicmp3-converter.git
cd musicmp3-converter
```

### 2. Crear entorno virtual
```bash
python3 -m venv .venv
source .venv/bin/activate # Linux/Mac
# .venv\Scripts\activate # Windows
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar el modelo (2 opciones)

#### Opción A: Con modelo pre-entrenado (Recomendado)
El repositorio incluye `profile.json` base (10 canciones, 40k notas):
```bash
# Copiar modelo base a tu carpeta local
cp profile.json ~/.musicmp3/

# ¡Listo! Modelo base instalado
# Verificar: ls -la ~/.musicmp3/profile.json
```

#### Opción B: Entrenar desde cero
Si preferís entrenar tu propio modelo:
```bash
# Ejecutar script de configuración
bash setup_model.sh

# O entrenar manualmente con:
python3 train_with_real_audio.py
```

### 5. Iniciar el servidor
```bash
musicmp3-server
# O: python -m musicmp3.server
```

### 6. Abrir en el navegador
````
http://127.0.0.1:8000
````
http://127.0.0.1:8000
````

## 📖 Uso

### Convertir una canción

1. **Subir audio**: Arrastrar archivo o pegar URL de YouTube
2. **Configurar**: Rango de notas, transposición, modo
3. **Convertir**: Click en "Convertir audio → NBS"
4. **Editar**: Ajustar notas en el piano roll
5. **Descargar**: Exportar a `.nbs` para Minecraft

### Entrenar el modelo

El modelo mejora automáticamente con cada conversión:

1. **Subir par NBS + Audio**: Sección "🧠 Entrenar modelo"
2. **Click "⬆ Subir par"**: Para cada canción
3. **Click "🔄 Reentrenar"**: Para actualizar el modelo
4. **Disfrutar**: Mejores conversiones automáticamente

### Piano Roll Interactivo

- **Playhead sincronizado**: Línea roja sigue la reproducción
- **Notas de colores**: Cada color es un instrumento diferente
- **Zoom**: Acercar/alejar con los botones 🔍+/🔍−
- **Edición**: Click y arrastrar para mover notas
- **Reproducción**: Click en "▶ Play" para escuchar

## 🎯 Modelos Disponibles

### Instrumentos Soportados
| ID | Instrumento | Rango |
|----|-------------|-------|
| 0  | Piano       | 0-87  |
| 1  | Bass Drum   | 0-87  |
| 2  | Snare       | 0-87  |
| 3  | Click       | 0-87  |
| 4  | Guitar      | 0-87  |
| 5  | Bass        | 0-87  |
| 6  | Bell        | 0-87  |
| 7  | Chime       | 0-87  |
| 8  | Flute       | 0-87  |
| 9  | Xylophone   | 0-87  |
| 10 | Iron Xylo   | 0-87  |
| 11 | Cow Bell    | 0-87  |

### Entrenamiento Actual
Por defecto, el modelo se entrena con:
- Bad Apple!!
- Believer
- Bohemian Rhapsody
- Teto - Birdbrain
- Y más...

**Base**: 10 canciones, 40,782 notas analizadas (10 instrumentos)

**Recomendado**: Entrenar con más canciones para mejor precisión (ver scripts abajo)

## 📁 Estructura del Proyecto

```
musicmp3-converter/
├── musicmp3/ # Código principal
│ ├── server.py # Servidor FastAPI
│ ├── converter.py # Conversión de audio
│ ├── nbs.py # Manipulación de NBS
│ ├── nbs_analyzer.py # Análisis y entrenamiento
│ ├── nbs_optimizer.py # Optimización de notas
│ ├── nbs_visualizer.py # Piano roll
│ └── static/ # Frontend web
│ ├── index.html
│ ├── app.js
│ ├── canvas.js
│ └── style.css
├── train_with_real_audio.py # Script de entrenamiento
├── setup_model.sh # Configuración automática
├── export_model.sh # Exportar modelo
├── import_model.sh # Importar modelo
├── profile.json # Modelo entrenado (compartible)
├── requirements.txt # Dependencias
└── README.md # Este archivo
```
musicmp3-converter/
├── musicmp3/              # Código principal
│   ├── server.py          # Servidor FastAPI
│   ├── converter.py       # Conversión de audio
│   ├── nbs.py             # Manipulación de NBS
│   ├── nbs_analyzer.py    # Análisis y entrenamiento
│   ├── nbs_optimizer.py   # Optimización de notas
│   ├── nbs_visualizer.py  # Piano roll
│   └── static/            # Frontend web
│       ├── index.html
│       ├── app.js
│       ├── canvas.js
│       └── style.css
├── train_with_real_audio.py  # Script de entrenamiento
├── setup_model.sh         # Configuración automática
├── requirements.txt       # Dependencias
└── README.md             # Este archivo
```

## 🔧 Comandos Útiles

### Entrenamiento
```bash
# Entrenar con canciones de YouTube
python3 train_with_real_audio.py

# Entrenar con 20+ canciones extra
python3 train_20_more.py

# Entrenamiento automático
bash setup_model.sh
```

### Exportar/Importar Modelo
```bash
# Exportar tu modelo entrenado (para compartir)
bash export_model.sh

# Importar modelo del repositorio
bash import_model.sh
```

### Servidor
```bash
# Iniciar servidor
musicmp3-server

# O directamente
python -m uvicorn musicmp3.server:app --host 127.0.0.1 --port 8000
```

## 📊 Progreso del Modelo

| Etapa | Canciones | Notas | Instrumentos |
|-------|-----------|-------|--------------|
| Inicial | 4 | 17,047 | 11 |
| Intermedio | 10 | 40,782 | 12 |
| **Actual** | **10** | **40,782** | **10** |

## 🔄 Compartir Modelos Entrenados

### Subir tu modelo a GitHub
Si entrenaste el modelo y querés compartirlo:

```bash
# 1. Asegurate de tener profile.json actualizado
ls -la ~/.musicmp3/profile.json

# 2. Copialo al repositorio
cp ~/.musicmp3/profile.json /path/to/musicmp3-converter/

# 3. Commitealo
git add profile.json
git commit -m "Update trained model: 39 songs, 134k notes"
git push
```

### Bajar modelo de GitHub
Si el repositorio tiene `profile.json`:

```bash
# 1. Clona el repositorio (ya incluye profile.json)
git clone https://github.com/tu-usuario/musicmp3-converter.git

# 2. Copia el profile.json a tu carpeta local
cp profile.json ~/.musicmp3/

# 3. ¡Listo! Tu modelo ya tiene las canciones entrenadas
```

### Estado del profile.json en GitHub
| Archivo | Estado | Descripción |
|---------|--------|-------------|
| `profile.json` | ✅ Incluido | Modelo base (10 canciones, 40k notas) |
| `*.mp3, *.wav` | ❌ Excluido | Audio con copyright (no subir) |
| `training_/` | ❌ Excluido | Datos temporales |

**Nota**: El `profile.json` incluido es un modelo base. Para mejorar la precisión, entrená tu propio modelo con:
```bash
python3 train_with_real_audio.py  # Descarga y entrena con canciones reales
```

## 🤝 Contribuir

1. Fork el proyecto
2. Crear rama (`git checkout -b feature/nueva-funcion`)
3. Commit cambios (`git commit -m 'Añadir nueva función'`)
4. Push (`git push origin feature/nueva-funcion`)
5. Abrir Pull Request

## 📝 Licencia

Este proyecto está bajo la licencia MIT.

## 🙏 Agradecimientos

- [NBSsongs](https://github.com/nickg2/NBSsongs) - Archivos NBS de ejemplo
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Descarga de audio
- [basic-pitch](https://github.com/spotify/basic-pitch) - Transcripción MIDI
- [Demucs](https://github.com/facebookresearch/demucs) - Separación de stems

## 🔗 Enlaces

- [Minecraft Note Block Studio](https://www.minecraftnoteblockstudio.com/)
- [Documentación de NBS](https://github.com/BigBangCS/NBSFormat)
- [Issue Tracker](https://github.com/tu-usuario/musicmp3-converter/issues)

---

**Hecho con ❤️ para la comunidad de Minecraft**
