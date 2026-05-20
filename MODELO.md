# 🧠 Guía del Modelo Entrenado

## ¿Qué es el profile.json?

El archivo `profile.json` contiene el modelo de IA entrenado con canciones reales. Incluye:
- Patrones de instrumentación (qué instrumentos usar en cada contexto)
- Rangos de notas más frecuentes por instrumento
- Velocidades promedio
- Estadísticas de uso

## Dos Opciones de Uso

### Opción 1: Modelo Base Incluido (Recomendado para empezar)

**Ventajas:**
- ✅ Funciona inmediatamente
- ✅ Ya tiene 10 canciones entrenadas (40k notas)
- ✅ Podés usarlo como base para seguir entrenando

**Pasos:**
```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/musicmp3-converter.git
cd musicmp3-converter

# 2. Importar el modelo base
bash import_model.sh

# 3. Iniciar el servidor
musicmp3-server
```

**¿Qué hacés con esta opción?**
- Usás el modelo base para convertir canciones
- Podés seguir entrenando con más canciones desde la web
- El modelo mejora con el tiempo

---

### Opción 2: Entrenar Desde Cero

**Ventajas:**
- ✅ Control total sobre los datos de entrenamiento
- ✅ Aprendés cómo funciona el proceso
- ✅ Modelo 100% personalizado

**Pasos:**
```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/musicmp3-converter.git
cd musicmp3-converter

# 2. Entrenar con canciones de YouTube
python3 train_with_real_audio.py

# 3. O entrenar con 20+ canciones extra
python3 train_20_more.py

# 4. Iniciar el servidor
musicmp3-server
```

**¿Qué hacés con esta opción?**
- Descargás canciones de YouTube automáticamente
- El modelo aprende de audio real (no sintético)
- Mayor precisión en conversiones

---

## Comparación

| Característica | Opción 1 (Base) | Opción 2 (Cero) |
|----------------|-----------------|-----------------|
| Tiempo inicial | Inmediato | 10-30 minutos |
| Canciones iniciales | 10 | 0 |
| Precisión inicial | Media | N/A (hay que entrenar) |
| Personalización | Alta (podés reentrenar) | Total |
| Recomendado para | Usuarios nuevos | Usuarios avanzados |

---

## Compartir tu Modelo

### Exportar (para subir a GitHub)

```bash
bash export_model.sh
```

Esto copia tu `profile.json` local al repositorio. Luego:

```bash
git add profile.json
git commit -m "Update model: X songs, Y notes"
git push
```

### Importar (de GitHub a tu PC)

```bash
bash import_model.sh
```

---

## ¿Dónde se guarda el modelo?

El modelo se guarda en: `~/.musicmp3/profile.json`

Los scripts `export_model.sh` e `import_model.sh` facilitan mover este archivo entre tu carpeta personal y el repositorio.

---

## Mejorar el Modelo

Para mejorar la precisión:

1. **Desde la web**:
   - Sección "🧠 Entrenar modelo"
   - Subí par NBS + Audio
   - Click "🔄 Reentrenar"

2. **Con scripts**:
   ```bash
   python3 train_with_real_audio.py  # Agrega más canciones
   python3 train_20_more.py          # 20+ canciones extra
   ```

3. **Automático**:
   ```bash
   bash setup_model.sh
   ```

---

## Notas Importantes

- ⚠️ **No subir audio con copyright a GitHub** (solo `profile.json`)
- ✅ `profile.json` es liviano (~140KB) y seguro de compartir
- 🎯 El modelo mejora con más canciones entrenadas
- 📊 Ver estadísticas: `cat ~/.musicmp3/profile.json | python3 -m json.tool`

---

## Stats Actuales del Modelo Base

```
Canciones: 10
Notas analizadas: 40,782
Instrumentos: 10
```

Para ver las tuyas:
```bash
cat ~/.musicmp3/profile.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Canciones: {d.get(\"songs_analyzed\", 0)}'); print(f'Notas: {d.get(\"total_notes_analyzed\", 0)}')"
```

