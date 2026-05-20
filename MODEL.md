# Trained Model Guide

## What is profile.json?

The `profile.json` file contains the AI model trained on real songs. It includes:
- Instrumentation patterns (which instruments to use in each context)
- Most frequent note ranges per instrument
- Average velocities
- Usage statistics

## Two Usage Options

### Option 1: Included Base Model (Recommended to start)

**Advantages:**
- Works immediately
- Already trained on 10 songs (40k notes)
- Can be used as a base for further training

**Steps:**
```bash
# 1. Clone the repository
git clone https://github.com/tu-usuario/musicmp3-converter.git
cd musicmp3-converter

# 2. Import the base model
bash import_model.sh

# 3. Start the server
musicmp3-server
```

**What you get:**
- Use the base model to convert songs right away
- Keep training with more songs from the web UI
- The model improves over time

---

### Option 2: Train From Scratch

**Advantages:**
- Full control over training data
- Learn how the process works
- 100% customized model

**Steps:**
```bash
# 1. Clone the repository
git clone https://github.com/tu-usuario/musicmp3-converter.git
cd musicmp3-converter

# 2. Train with YouTube songs
python train_with_real_audio.py

# 3. Or train with 20+ extra songs
python train_20_more.py

# 4. Start the server
musicmp3-server
```

**What you get:**
- Downloads YouTube songs automatically
- Model learns from real audio (not synthetic)
- Higher conversion accuracy

---

## Comparison

| Feature | Option 1 (Base) | Option 2 (Scratch) |
|---------|----------------|-------------------|
| Time to start | Immediate | 10-30 minutes |
| Initial songs | 10 | 0 |
| Initial accuracy | Medium | N/A (needs training) |
| Customization | High (can retrain) | Total |
| Recommended for | New users | Advanced users |

---

## Sharing Your Model

### Export (to upload to GitHub)

```bash
bash export_model.sh
```

This copies your local `profile.json` to the repository. Then:

```bash
git add profile.json
git commit -m "Update model: X songs, Y notes"
git push
```

### Import (from GitHub to your PC)

```bash
bash import_model.sh
```

---

## Where is the model stored?

The model is stored at: `~/.musicmp3/profile.json`

The `export_model.sh` and `import_model.sh` scripts make it easy to move this file between your local folder and the repository.

---

## Improving the Model

To improve accuracy:

1. **From the web UI**:
   - "Train model" section
   - Upload NBS + Audio pair
   - Click "Retrain"

2. **With scripts**:
   ```bash
   python train_with_real_audio.py  # Add more songs
   python train_20_more.py          # 20+ extra songs
   ```

3. **Automated**:
   ```bash
   bash setup_model.sh
   ```

---

## Important Notes

- Do not upload copyrighted audio to GitHub (only `profile.json`)
- `profile.json` is lightweight (~140KB) and safe to share
- The model improves with more trained songs
- View stats: `cat ~/.musicmp3/profile.json | python -m json.tool`

---

## Current Base Model Stats

```
Songs: 10
Notes analyzed: 40,782
Instruments: 10
```

To view your stats:
```bash
cat ~/.musicmp3/profile.json | python -c "import sys,json; d=json.load(sys.stdin); print(f'Songs: {d.get(\"songs_analyzed\", 0)}'); print(f'Notes: {d.get(\"total_notes_analyzed\", 0)}')"
```
