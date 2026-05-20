import io
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from .nbs_playback import parse_nbs

INSTRUMENT_NAMES = {
    0: "Piano", 1: "Bass Drum", 2: "Snare", 3: "Click",
    4: "Guitar", 5: "Bass", 6: "Bell", 7: "Chime",
    8: "Flute", 9: "Xylophone", 10: "Iron Xylophone",
    11: "Cow Bell", 12: "Didgeridoo", 13: "Bit",
    14: "Banjo", 15: "Pling",
}

MC_NOTE_NAMES = ["F#3","G3","G#3","A3","A#3","B3",
    "C4","C#4","D4","D#4","E4","F4","F#4","G4","G#4","A4","A#4","B4",
    "C5","C#5","D5","D#5","E5","F5","F#5"]

MC_LOWEST_KEY = 33

def key_to_mc_name(key: int) -> str:
    idx = key - MC_LOWEST_KEY
    if 0 <= idx < len(MC_NOTE_NAMES):
        return MC_NOTE_NAMES[idx]
    return f"Key{key}"


def generate_piano_roll(nbs_path: str, max_width: int = 1200, max_height: int = 600) -> bytes:
    data = parse_nbs(nbs_path)
    notes = data["notes"]
    if not notes:
        return b""

    tick_sec = data["tick_seconds"]
    max_time = max(n["start_time"] for n in notes) + 2.0

    keys = sorted(set(n["key"] for n in notes))
    min_key = min(keys)
    max_key = max(keys)
    key_span = max_key - min_key + 1

    fig_height = max(4, key_span * 0.15)
    fig, ax = plt.subplots(figsize=(max_width / 100, min(fig_height, max_height / 100)), dpi=100)
    ax.set_xlim(0, max_time)
    ax.set_ylim(min_key - 0.5, max_key + 0.5)
    ax.set_xlabel("Time (seconds)", fontsize=9)
    ax.set_ylabel("NBS Key / Minecraft Note", fontsize=9)
    ax.set_title(f"{data['song_name']} — Piano Roll ({len(notes)} notes)", fontsize=10)

    # Y-axis: show key numbers and Minecraft note names
    step = max(1, key_span // 20)
    tick_keys = range(min_key, max_key + 1, step)
    ax.set_yticks(list(tick_keys))
    ax.set_yticklabels([f"{k} ({key_to_mc_name(k)})" for k in tick_keys], fontsize=6)

    cmap = plt.colormaps.get_cmap("tab10")
    inst_colors = {}
    dur = max(0.08, min(0.8, 1.0 / data["tempo_bps"] * 4))

    for i, note in enumerate(notes):
        inst = note["instrument"]
        if inst not in inst_colors:
            inst_colors[inst] = cmap(inst % 10)
        color = inst_colors[inst]
        rect = Rectangle(
            (note["start_time"], note["key"] - 0.4),
            dur,
            0.8,
            facecolor=color,
            alpha=0.7,
            edgecolor="none",
        )
        ax.add_patch(rect)

    # Legend for instruments
    used_insts = sorted(set(n["instrument"] for n in notes))
    legend_items = [
        Rectangle((0, 0), 1, 1, facecolor=inst_colors.get(i, "gray"), alpha=0.7)
        for i in used_insts
    ]
    legend_labels = [INSTRUMENT_NAMES.get(i, f"Inst {i}") for i in used_insts]
    if legend_items:
        ax.legend(
            legend_items, legend_labels,
            loc="upper right", fontsize=7, ncol=min(4, len(legend_items)),
        )

    ax.invert_yaxis()
    ax.tick_params(labelsize=7)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def generate_interactive_piano_roll(nbs_path: str, audio_path: str | None = None) -> str:
    """Generate interactive HTML piano roll with synchronized playback line."""
    data = parse_nbs(nbs_path)
    notes = data["notes"]
    if not notes:
        return "<html><body>No notes</body></html>"

    # Convert notes to JSON-serializable format
    notes_data = []
    for n in notes:
        notes_data.append({
            "start_time": n["start_time"],
            "key": n["key"],
            "instrument": n["instrument"],
            "velocity": n.get("velocity", 100),
        })

    max_time = max(n["start_time"] for n in notes) + 2.0
    keys = sorted(set(n["key"] for n in notes))
    min_key = min(keys)
    max_key = max(keys)
    
    instrument_names = INSTRUMENT_NAMES
    
    audio_html = f'<audio id="audio" src="{audio_path}" preload="auto"></audio>' if audio_path else ''
    roll_height = min(max_key - min_key + 2, 50) * 15
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{data["song_name"]} - Interactive Piano Roll</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h2 {{ color: #00d9ff; }}
        #roll {{ 
            background: #16213e; 
            border: 2px solid #0f3460; 
            border-radius: 8px;
            position: relative;
            overflow: hidden;
        }}
        .note {{
            position: absolute;
            border-radius: 2px;
            opacity: 0.8;
            transition: opacity 0.2s;
        }}
        .note:hover {{ opacity: 1; z-index: 10; }}
        .playhead {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 3px;
            background: #ff006e;
            z-index: 100;
            box-shadow: 0 0 10px #ff006e;
        }}
        .controls {{
            margin: 20px 0;
            padding: 15px;
            background: #16213e;
            border-radius: 8px;
        }}
        button {{
            background: #00d9ff;
            color: #1a1a2e;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            margin-right: 10px;
        }}
        button:hover {{ background: #00b8e6; }}
        .time-display {{
            font-size: 18px;
            color: #00d9ff;
            margin-left: 15px;
        }}
        .legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 10px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 3px;
        }}
        .key-label {{
            position: absolute;
            right: 5px;
            color: #aaa;
            font-size: 10px;
            transform: translateY(-50%);
        }}
        .key-row {{
            position: absolute;
            left: 0;
            right: 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        audio {{ margin-top: 15px; width: 100%; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>🎹 {data["song_name"]} - Interactive Piano Roll</h2>
        <p style="color: #888;">{len(notes)} notes | Duration: {max_time:.1f}s</p>
        
        <div class="controls">
            <button id="playBtn">▶ Play</button>
            <button id="pauseBtn">⏸ Pause</button>
            <button id="resetBtn">⏹ Reset</button>
            <span class="time-display" id="timeDisplay">0.0s</span>
            {audio_html}
        </div>
        
        <div id="roll" style="height: {roll_height}px; position: relative;">
            <div class="playhead" id="playhead"></div>
        </div>
        
        <div class="legend" id="legend"></div>
    </div>
    
    <script>
        const notes = {json.dumps(notes_data)};
        const maxTime = {max_time};
        const minKey = {min_key};
        const maxKey = {max_key};
        const keyRange = maxKey - minKey + 1;
        const instNames = {json.dumps(instrument_names)};
        
        // Colors for instruments
        const colors = ["#00d9ff", "#ff006e", "#febb02", "#00ff88", "#a855f7", "#f97316", "#ec4899", "#14b8a6"];
        const instColors = {{}};
        notes.forEach(n => {{
            if (!instColors[n.instrument]) {{
                instColors[n.instrument] = colors[n.instrument % colors.length];
            }}
        }});
        
        // Calculate dimensions
        const roll = document.getElementById("roll");
        const rollHeight = roll.offsetHeight;
        const rowHeight = rollHeight / (keyRange || 1);
        const pixelsPerSecond = roll.offsetWidth / maxTime * 0.95;
        
        roll.style.width = (maxTime * 200) + "px";
        
        // Create key rows
        for (let key = minKey; key <= maxKey; key++) {{
            const row = document.createElement("div");
            row.className = "key-row";
            row.style.bottom = ((key - minKey) * rowHeight) + "px";
            roll.appendChild(row);
            
            const label = document.createElement("span");
            label.className = "key-label";
            label.textContent = key + " (Key " + key + ")";
            row.appendChild(label);
        }}
        
        // Create note blocks
        notes.forEach(n => {{
            const note = document.createElement("div");
            note.className = "note";
            note.style.left = (n.start_time * pixelsPerSecond) + "px";
            note.style.bottom = ((n.key - minKey) * rowHeight + rowHeight * 0.1) + "px";
            note.style.width = Math.max(15, pixelsPerSecond * 0.15) + "px";
            note.style.height = (rowHeight * 0.8) + "px";
            note.style.background = instColors[n.instrument];
            note.title = `Key: ${{n.key}} | Inst: ${{instNames[n.instrument] || n.instrument}} | Time: ${{n.start_time.toFixed(2)}}s`;
            roll.appendChild(note);
        }});
        
        // Legend
        const legend = document.getElementById("legend");
        Object.entries(instColors).forEach(([inst, color]) => {{
            const item = document.createElement("div");
            item.className = "legend-item";
            item.innerHTML = `<div class="legend-color" style="background: ${{color}}"></div><span>${{instNames[inst] || "Inst " + inst}}</span>`;
            legend.appendChild(item);
        }});
        
        // Playback controls - synchronized with audio
        const playhead = document.getElementById("playhead");
        const timeDisplay = document.getElementById("timeDisplay");
        const audio = document.getElementById("audio");
        let animationId = null;
        
        function updatePlayhead() {{
            const currentTime = audio ? audio.currentTime : 0;
            const pixels = currentTime * pixelsPerSecond;
            playhead.style.left = pixels + "px";
            timeDisplay.textContent = currentTime.toFixed(1) + "s";
            
            if (audio && !audio.paused && !audio.ended) {{
                animationId = requestAnimationFrame(updatePlayhead);
            }}
        }}
        
        document.getElementById("playBtn").onclick = () => {{
            if (audio && audio.play) {{
                audio.play();
                updatePlayhead();
            }}
        }};
        
        document.getElementById("pauseBtn").onclick = () => {{
            if (audio && audio.pause) {{
                audio.pause();
            }}
            if (animationId) cancelAnimationFrame(animationId);
        }};
        
        document.getElementById("resetBtn").onclick = () => {{
            if (audio) {{
                audio.pause();
                audio.currentTime = 0;
            }}
            if (animationId) cancelAnimationFrame(animationId);
            playhead.style.left = "0px";
            timeDisplay.textContent = "0.0s";
        }};
        
        // Sync playhead when seeking in audio
        if (audio) {{
            audio.addEventListener('timeupdate', () => {{
                if (!audio.paused) {{
                    updatePlayhead();
                }}
            }});
        }}
    </script>
</body>
</html>'''
    return html


def generate_key_histogram(nbs_path: str, max_width: int = 600, max_height: int = 250) -> bytes:
    data = parse_nbs(nbs_path)
    notes = data["notes"]
    if not notes:
        return b""

    keys = [n["key"] for n in notes]
    min_key = min(keys)
    max_key = max(keys)

    fig, ax = plt.subplots(figsize=(max_width / 100, max_height / 100), dpi=100)
    bins = range(min_key, max_key + 2)
    counts, _, patches = ax.hist(keys, bins=bins, color="steelblue", alpha=0.8, edgecolor="white", linewidth=0.5)

    ax.set_xlabel("NBS Key", fontsize=8)
    ax.set_ylabel("Note count", fontsize=8)
    ax.set_title(f"Key distribution (keys {min_key}–{max_key}, {len(notes)} notes)", fontsize=9)
    ax.tick_params(labelsize=6)

    # Mark Minecraft audible range
    ax.axvspan(32.5, 57.5, color="green", alpha=0.08, label="Minecraft range (F#3–F#5)")
    if 33 <= min_key <= 57 or 33 <= max_key <= 57:
        ax.legend(fontsize=6, loc="upper right")

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
