import os, uuid, shutil, json, tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from musicmp3.downloader import download_song
from musicmp3.converter import convert_file
from musicmp3.nbs import modify_nbs_file, _build_nbs_buf
from musicmp3.nbs_playback import render_nbs_to_wav, parse_nbs
from musicmp3.nbs_visualizer import generate_piano_roll, generate_interactive_piano_roll
from musicmp3.nbs_optimizer import optimize_nbs
from musicmp3.nbs_analyzer import learn_profile, save_profile, load_profile, apply_profile_to_converter, learn_audio_model
from musicmp3.nbs import INSTRUMENTS, STEM_INSTRUMENT_MAP

SESSIONS_DIR = Path(tempfile.gettempdir()) / "musicmp3_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Persistent profile storage (survives reboot)
PROFILES_DIR = Path.home() / ".musicmp3"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_PATH = PROFILES_DIR / "profile.json"

app = FastAPI(title="MusicMP3 → NBS")


def _session_path(session_id: str) -> Path:
    p = SESSIONS_DIR / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p


@app.post("/api/session")
def create_session():
    sid = uuid.uuid4().hex[:12]
    _session_path(sid)
    return {"session_id": sid}


@app.post("/api/upload-nbs")
async def upload_nbs(
    session_id: str = Form(...),
    file: Optional[UploadFile] = None,
):
    """Subir un archivo .nbs directamente para edición/reproducción."""
    sess = _session_path(session_id)
    
    if not file or not file.filename:
        raise HTTPException(400, "No file provided")
    
    ext = Path(file.filename).suffix.lower()
    if ext != '.nbs':
        raise HTTPException(400, "File must be .nbs format")
    
    # Guardar archivo
    input_path = str(sess / "input.nbs")
    with open(input_path, "wb") as f:
        f.write(await file.read())
    
    # Copiar a song.nbs
    from shutil import copy2
    song_path = str(sess / "song.nbs")
    copy2(input_path, song_path)
    
    # Parsear para obtener info
    from musicmp3.nbs_playback import parse_nbs
    data = parse_nbs(song_path)
    
    return {
        "status": "ok",
        "filename": file.filename,
        "notes": len(data.get("notes", [])),
        "max_layer": data.get("max_layer", 1),
    }


@app.post("/api/convert")
async def convert(
    session_id: str = Form(...),
    query: Optional[str] = Form(None),
    target_low: int = Form(33),
    target_high: int = Form(80),
    transpose: int = Form(0),
    file: Optional[UploadFile] = None,
    profile_path: Optional[str] = Form(None),
    mode: str = Form("full"),
):
    sess = _session_path(session_id)

    # Auto-use profile if none specified and it exists
    if profile_path is None and PROFILE_PATH.exists():
        profile_path = str(PROFILE_PATH)

    if file and file.filename:
        ext = Path(file.filename).suffix.lower()
        input_path = str(sess / f"input{ext}")
        with open(input_path, "wb") as f:
            f.write(await file.read())
        is_nbs = ext == ".nbs"
    elif query and query.strip():
        try:
            input_path = str(download_song(query.strip()))
        except Exception as e:
            raise HTTPException(400, f"Download failed: {e}")
        is_nbs = False
    else:
        raise HTTPException(400, "Provide a song name or upload a file")

    try:
        if is_nbs:
            out_path = str(sess / "song.nbs")
            result = modify_nbs_file(input_path, out_path,
                                     target_low=target_low, target_high=target_high,
                                     transpose=transpose)
            msg = "NBS modified"
        else:
            result = convert_file(input_path,
                                  target_low=target_low, target_high=target_high,
                                  transpose=transpose,
                                  profile_path=profile_path,
                                  mode=mode)
            msg = "Done"

        if not result:
            raise HTTPException(500, "Conversion produced no output")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

    # Copy result to session if not already there
    if Path(result).parent != sess:
        shutil.copy2(result, sess / "song.nbs")

    # Render preview
    nbs_path = str(sess / "song.nbs")
    if not (sess / "song.nbs").exists():
        raise HTTPException(500, "No NBS file produced")

    return {"status": msg, "session_id": session_id, "nbs": nbs_path}


@app.get("/api/session/{session_id}/notes")
def get_notes(session_id: str):
    sess = _session_path(session_id)
    nbs_path = sess / "song.nbs"
    if not nbs_path.exists():
        raise HTTPException(404, "No song in this session")
    data = parse_nbs(str(nbs_path))
    return {
        "notes": data["notes"],
        "tempo_bps": data.get("tempo_bps", 10),
        "song_name": data.get("song_name", ""),
        "max_layer": data.get("max_layer", 1),
        "duration": max((n["start_time"] for n in data["notes"]), default=0) if data["notes"] else 0,
        "custom_instruments": data.get("custom_instruments", {}),
    }


def _key_to_name(k):
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    midi = k + 21
    return f"{names[midi % 12]}{midi // 12 - 1}"


@app.put("/api/session/{session_id}/notes")
async def save_notes(session_id: str, body: dict):
    sess = _session_path(session_id)
    nbs_path = sess / "song.nbs"
    if not nbs_path.exists():
        raise HTTPException(404, "No song in this session")

    new_notes = body.get("notes", [])
    for n in new_notes:
        n["key"] = max(0, min(87, int(n.get("key", 0))))
        n["velocity"] = max(0, min(100, int(n.get("velocity", 100))))
        n["panning"] = max(0, min(200, int(n.get("panning", 100))))
        n["pitch"] = int(n.get("pitch", -1))
        n.setdefault("layer", 0)
        n.setdefault("instrument", 0)

    new_notes.sort(key=lambda x: (x["tick"], x["layer"]))
    max_tick = max((n["tick"] for n in new_notes), default=0) + 1

    orig = parse_nbs(str(nbs_path))
    max_layer = orig.get("max_layer", 1)
    song_name = orig.get("song_name", "")
    tempo_bps = orig.get("tempo_bps", 10)
    tempo_raw = max(1, min(1000, int(tempo_bps * 100)))
    orig_layers = orig.get("layers", [])
    layers = [
        orig_layers[i] if i < len(orig_layers) else {"name": f"Layer {i+1}", "volume": 100, "stereo": 100}
        for i in range(max_layer)
    ]
    custom_instruments = orig.get("custom_instruments", {})

    buf = _build_nbs_buf(max_tick, max_layer, tempo_raw, new_notes, layers, song_name, custom_instruments)
    with open(nbs_path, "wb") as f:
        f.write(buf)

    return {"status": "ok", "note_count": len(new_notes)}


@app.post("/api/session/{session_id}/render")
def render(session_id: str):
    sess = _session_path(session_id)
    nbs_path = sess / "song.nbs"
    if not nbs_path.exists():
        raise HTTPException(404, "No song in this session")

    try:
        wav = render_nbs_to_wav(str(nbs_path), str(sess / "preview.wav"))
        pr_bytes = generate_piano_roll(str(nbs_path))
        if pr_bytes:
            with open(sess / "piano_roll.png", "wb") as f:
                f.write(pr_bytes)
        return {"wav": f"/api/session/{session_id}/audio", "piano_roll": f"/api/session/{session_id}/piano_roll"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/session/{session_id}/audio")
def get_audio(session_id: str):
    sess = _session_path(session_id)
    wav = sess / "preview.wav"
    if not wav.exists():
        raise HTTPException(404, "No preview — call render first")
    return FileResponse(str(wav), media_type="audio/wav", filename="preview.wav")


@app.get("/api/session/{session_id}/piano_roll")
def get_piano_roll(session_id: str):
    sess = _session_path(session_id)
    png = sess / "piano_roll.png"
    if not png.exists():
        raise HTTPException(404, "No piano roll — call render first")
    return FileResponse(str(png), media_type="image/png", filename="piano_roll.png")


@app.get("/api/session/{session_id}/piano_roll_html")
def get_interactive_piano_roll(session_id: str):
    """Generate interactive piano roll with synchronized playback line."""
    sess = _session_path(session_id)
    nbs_path = sess / "song.nbs"
    if not nbs_path.exists():
        raise HTTPException(404, "No song in this session")
    
    # Check for audio file
    audio_path = sess / "preview.wav"
    audio_param = str(audio_path) if audio_path.exists() else None
    
    html_content = generate_interactive_piano_roll(str(nbs_path), audio_param)
    
    # Save HTML file
    html_file = sess / "piano_roll.html"
    with open(html_file, "w") as f:
        f.write(html_content)
    
    return FileResponse(str(html_file), media_type="text/html", filename="piano_roll.html")


@app.get("/api/session/{session_id}/nbs")
def download_nbs(session_id: str):
    sess = _session_path(session_id)
    nbs = sess / "song.nbs"
    if not nbs.exists():
        raise HTTPException(404, "No song in this session")
    return FileResponse(str(nbs), media_type="application/octet-stream", filename="song.nbs")


@app.post("/api/session/{session_id}/optimize")
def optimize(session_id: str, add_missing: bool = True, remove_silent: bool = True):
    """
    Optimize NBS by comparing with original audio.
    
    Features:
    - Change instruments based on timbre matching
    - Add missing notes detected in audio
    - Remove notes in silent sections  
    - Adjust velocities based on energy
    """
    sess = _session_path(session_id)
    nbs_path = sess / "song.nbs"
    if not nbs_path.exists():
        raise HTTPException(404, "No song in this session")

    # Find the original audio file in the session
    audio_exts = [".mp3", ".wav", ".flac", ".m4a", ".ogg"]
    audio_path = None
    for f in sess.iterdir():
        if f.suffix.lower() in audio_exts:
            audio_path = str(f)
            break

    if not audio_path:
        raise HTTPException(400, "No original audio file found — optimize only works with MP3/WAV uploads")

    try:
        # Use enhanced optimizer
        from musicmp3.nbs_optimizer import optimize_nbs as enhance_optimizer
        
        result = enhance_optimizer(
            str(nbs_path), 
            audio_path,
            add_missing=add_missing,
            remove_silent=remove_silent
        )
        
        optimized = result['optimized_notes']
        changes = result['changes']
        stats = result['stats']

        if not optimized:
            raise HTTPException(500, "Optimization produced no output")

        # Save optimized notes back to NBS
        orig = parse_nbs(str(nbs_path))
        
        # Get max tick and layer from original
        max_tick = max((n["tick"] for n in optimized), default=0) + 1
        max_layer = max((n.get("layer", 0) for n in optimized), default=0) + 1
        
        # Build new NBS buffer
        new_notes = []
        for n in optimized:
            new_notes.append({
                "tick": n.get("tick", n.get("tick", 0)),
                "key": n.get("key", 0),
                "layer": n.get("layer", 0),
                "instrument": n.get("instrument", 0),
                "velocity": n.get("velocity", 100),
                "panning": n.get("panning", 100),
                "pitch": n.get("pitch", -1),
            })
        
        layers = orig.get("layers", [])
        if not layers:
            layers = [{"name": "Layer 1", "volume": 100, "stereo": 100}]
        
        custom_instruments = orig.get("custom_instruments", {})
        tempo_raw = int(orig.get("tempo_bps", 10) * 100)
        song_name = orig.get("song_name", "")
        
        buf = _build_nbs_buf(max_tick, max_layer, tempo_raw, new_notes, layers, song_name, custom_instruments)
        with open(nbs_path, "wb") as f:
            f.write(buf)
        
        return {"status": "ok", "changes": len(changes), "stats": stats, "changed_notes": changes[:200]}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/profile/generate")
async def generate_profile(nbs_dir: str = Form(...)):
    """Scan a directory of NBS files and generate a conversion profile."""
    try:
        profile = learn_profile(nbs_dir)
        if not profile:
            raise HTTPException(400, "No valid NBS files found in directory")
        # Store in a well-known location
        profile_path = PROFILE_PATH
        save_profile(profile, str(profile_path))
        return {
            "status": "ok",
            "songs_analyzed": profile["songs_analyzed"],
            "total_notes": profile["total_notes_analyzed"],
            "instrument_usage": profile.get("instrument_usage", {}),
            "recommended_mapping": profile.get("recommended_mapping", {}),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/profile")
def get_profile():
    profile_path = PROFILE_PATH
    if not profile_path.exists():
        raise HTTPException(404, "No profile generated yet. POST /api/profile/generate first.")
    profile = load_profile(str(profile_path))
    return {
        "songs_analyzed": profile["songs_analyzed"],
        "total_notes": profile["total_notes_analyzed"],
        "recommended_mapping": profile.get("recommended_mapping", {}),
        "instrument_usage": profile.get("instrument_usage", {}),
    }


@app.post("/api/profile/apply")
def apply_profile():
    """Apply the learned profile to override the default converter mapping."""
    profile_path = PROFILE_PATH
    if not profile_path.exists():
        raise HTTPException(404, "No profile found")
    profile = load_profile(str(profile_path))
    new_stem_map, _ = apply_profile_to_converter(profile, STEM_INSTRUMENT_MAP, INSTRUMENTS)
    return {
        "status": "ok",
        "old_mapping": STEM_INSTRUMENT_MAP,
        "new_mapping": new_stem_map,
    }


@app.get("/api/profile/model")
def get_audio_model():
    """Return the audio→instrument model details."""
    profile_path = PROFILE_PATH
    if not profile_path.exists():
        raise HTTPException(404, "No profile")
    profile = load_profile(str(profile_path))
    model = profile.get("audio_model")
    if not model:
        raise HTTPException(404, "No audio model in profile. Add NBS+audio pairs.")
    return {
        "songs_analyzed": model["songs_analyzed"],
        "notes_extracted": model["notes_extracted"],
        "instruments": {
            k: {"name": v["name"], "count": v["count"], "mean": v["mean"]}
            for k, v in model["model"].get("instruments", {}).items()
        },
    }


@app.post("/api/profile/upload-pair")
async def upload_training_pair(
    nbs: UploadFile = Form(...),
    audio: UploadFile = Form(...),
):
    """Upload a single NBS+audio pair for training."""
    # Save the pair in a training directory (no profile needed)
    train_dir = PROFILES_DIR / "training"
    train_dir.mkdir(exist_ok=True)

    # Save NBS with its original name
    nbs_name = Path(nbs.filename).name
    nbs_path = train_dir / nbs_name
    with open(nbs_path, "wb") as f:
        f.write(await nbs.read())

    # Save audio with the SAME stem as the NBS (so find_pairs matches them)
    audio_ext = Path(audio.filename).suffix.lower()
    audio_name = Path(nbs_name).stem + audio_ext
    audio_path = train_dir / audio_name
    with open(audio_path, "wb") as f:
        f.write(await audio.read())

    return {"status": "ok", "nbs": nbs_name, "audio": audio_name,
            "note": "Run POST /api/profile/relearn to train the model"}


@app.post("/api/profile/gen-base")
def generate_base_profile():
    """Create a minimal base profile (no audio model) from training dir."""
    profile = {"songs_analyzed": 0, "total_notes_analyzed": 0,
               "instrument_usage": {}, "role_recommendations": {},
               "recommended_mapping": {}, "source_files": []}

    # If there are NBS files in training dir, analyze them
    train_dir = PROFILES_DIR / "training"
    if train_dir.exists():
        nbs_analysis = learn_profile(str(train_dir))
        if nbs_analysis:
            profile = nbs_analysis

    profile_path = PROFILE_PATH
    save_profile(profile, str(profile_path))
    return {"status": "ok", "songs_analyzed": profile["songs_analyzed"]}


@app.post("/api/profile/relearn")
def retrain_audio_model():
    """Re-train the audio model using all uploaded pairs."""
    train_dir = PROFILES_DIR / "training"
    profile_path = PROFILE_PATH

    # Load existing profile or create a basic one
    if profile_path.exists():
        profile = load_profile(str(profile_path))
    else:
        profile = {"songs_analyzed": 0, "total_notes_analyzed": 0,
                   "instrument_usage": {}, "role_recommendations": {},
                   "recommended_mapping": {}, "source_files": []}

    # If no training dir exists but profile already has an audio model, return it
    if not train_dir.exists() or not any(train_dir.iterdir()):
        existing_model = profile.get("audio_model")
        if existing_model:
            print("[server] No new training data, using existing audio model from profile")
            return {"status": "ok", "notes_extracted": existing_model.get("notes_extracted", 0),
                    "instruments_trained": len(existing_model.get("model", {}).get("instruments", {}))}
        raise HTTPException(400, "No training data. Upload NBS+audio pairs first.")

    # Debug: list files in training dir for diagnostics
    files_list = [f.name for f in train_dir.iterdir()]
    print(f"[server] Training dir files: {files_list}")

    # Train audio model from files already in the training dir
    result = learn_audio_model(str(train_dir))
    if result:
        profile["audio_model"] = result
        profile["songs_analyzed"] = result["songs_analyzed"]
        profile["total_notes_analyzed"] = result["notes_extracted"]
        save_profile(profile, str(profile_path))
        return {"status": "ok", "notes_extracted": result["notes_extracted"],
                "instruments_trained": len(result["model"]["instruments"])}
    else:
        nbs_count = sum(1 for f in files_list if f.endswith(".nbs"))
        audio_count = sum(1 for f in files_list if f.endswith((".mp3", ".wav", ".flac", ".m4a", ".ogg")))
        msg = f"No valid NBS+audio pairs. Found {nbs_count} NBS, {audio_count} audio files. "
        msg += "Each .nbs needs a matching audio file with the same name (e.g. song.nbs + song.mp3). Check server console for details."
        raise HTTPException(400, msg)


# Mount static frontend
HERE = Path(__file__).parent
static_dir = HERE / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


def main():
    import signal
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    try:
        server.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
