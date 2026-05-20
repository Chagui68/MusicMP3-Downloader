#!/usr/bin/env python3
"""
Download REAL audio from YouTube and train the model properly.
This will create ACTUAL useful training data.
"""
import os, sys, subprocess, json, shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
# Use the SAME training directory as the server
TRAINING_DIR = Path.home() / ".musicmp3" / "training"
NBS_SONGS_DIR = PROJECT_DIR / "NBSsongs" / "songs"

# Ensure training dir exists
TRAINING_DIR.mkdir(parents=True, exist_ok=True)

# Songs that DEFINITELY exist on YouTube with exact names
SONG_MAP = {
    "Pallet Town Theme.nbs": "Pokemon Pallet Town theme song original",
    "Axel F.nbs": "Crazy Frog Axel F original",
    " clocks.nbs": "Coldplay Clocks official audio",
    "Moonlight Sonata.nbs": "Beethoven Moonlight Sonata 3rd movement",
    "fireflies.nbs": "Owl City Fireflies official",
    "still alive.nbs": "Still Alive Portal Game soundtrack",
    "Linus and Lucy.nbs": "Linus and Lucy Vince Guaraldi piano",
    "Take On Me.nbs": "A-ha Take On Me original",
    "Never Gonna Give You Up.nbs": "Rick Astley Never Gonna Give You Up",
    "despacito.nbs": "Despacito Luis Fonsi original",
}

def print_header(text):
    print(f"\n{'='*70}\n {text}\n{'='*70}\n")

def download_audio(search_query, output_name):
    """Download audio from YouTube."""
    try:
        output_path = TRAINING_DIR / f"{output_name}.mp3"
        
        cmd = [
            'yt-dlp',
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', '128K',
            '--output', str(output_path),
            '--max-filesize', '20M',
            '-f', 'bestaudio',
            f'ytsearch1:{search_query}'
        ]
        
        print(f"  Downloading: {search_query}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        if output_path.exists():
            print(f"  ✓ Downloaded: {output_name}")
            return output_path
        else:
            print(f"  ✗ Failed: {output_name}")
            return None
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None

def main():
    print_header("🎵 Real Audio Training")
    print("This will download REAL songs from YouTube and train the model")
    
    TRAINING_DIR.mkdir(exist_ok=True)
    
    if not NBS_SONGS_DIR.exists():
        print("NBSsongs directory not found!")
        return False
    
    # Find matching NBS files
    pairs_created = 0
    
    for nbs_filename, search_query in SONG_MAP.items():
        nbs_path = NBS_SONGS_DIR / nbs_filename
        
        # Check if NBS exists (try variations)
        if not nbs_path.exists():
            # Try finding similar name
            all_nbs = list(NBS_SONGS_DIR.glob(f"*{nbs_filename.split()[0]}*"))
            if all_nbs:
                nbs_path = all_nbs[0]
                print(f"  Found similar: {nbs_path.name}")
            else:
                print(f"  ✗ NBS not found: {nbs_filename}")
                continue
        
        # Copy NBS to training dir
        dest_nbs = TRAINING_DIR / nbs_path.name
        if not dest_nbs.exists():
            shutil.copy2(nbs_path, dest_nbs)
        
        # Download audio
        audio_name = nbs_path.stem
        audio_path = download_audio(search_query, audio_name)
        
        if audio_path:
            pairs_created += 1
            print(f"  ✓ Pair created: {nbs_path.name} + audio")
        else:
            # Remove NBS if no audio
            if dest_nbs.exists():
                dest_nbs.unlink()
    
    if pairs_created == 0:
        print("\n❌ No pairs created! Check your internet connection.")
        return False
    
    print(f"\n✅ Created {pairs_created} training pairs")
    
    # Train the model
    print_header("Training with Real Audio")
    
    try:
        from musicmp3.nbs_analyzer import learn_audio_model
        import json as json_module
        
        result = learn_audio_model(str(TRAINING_DIR))
        
        if result and result.get('model', {}).get('instruments'):
            print(f"\n✅ Training completed!")
            print(f"  Songs: {result.get('songs_analyzed', 0)}")
            print(f"  Notes: {result.get('notes_extracted', 0)}")
            print(f"  Instruments: {len(result['model']['instruments'])}")
            
            # Save profile
            profile = {
                "songs_analyzed": result.get('songs_analyzed', 0),
                "total_notes_analyzed": result.get('notes_extracted', 0),
                "instrument_usage": {},
                "role_recommendations": {"percussion": [1,2,3], "bass": [5,0], "melody": [0,6,9]},
                "recommended_mapping": {
                    "stem_to_instrument": {"bass": [5], "drums": [1], "other": [0]},
                    "layer_assignments": {"bass": 5, "drums": 1, "melody": 0},
                    "key_range_target": {"min": 33, "max": 80}
                },
                "audio_model": result,
                "source_files": [f.name for f in TRAINING_DIR.glob("*.nbs")]
            }
            
            profile_path = PROJECT_DIR / "profile.json"
            with open(profile_path, 'w') as f:
                json_module.dump(profile, f, indent=2)
            
            print(f"\n✅ Profile saved to: {profile_path}")
            print("\n" + "="*70)
            print("MODEL READY! Restart the server to use it.")
            print("="*70)
            return True
            
    except Exception as e:
        print(f"\n✗ Training error: {e}")
        import traceback
        traceback.print_exc()
    
    return False

if __name__ == "__main__":
    # Check for yt-dlp
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, timeout=5)
    except:
        print("Installing yt-dlp...")
        subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"])
    
    success = main()
    sys.exit(0 if success else 1)
