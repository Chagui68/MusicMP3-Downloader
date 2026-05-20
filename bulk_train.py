#!/usr/bin/env python3
"""Bulk train with all NBS files using synthetic audio."""
import os, sys, subprocess, shutil, json
from pathlib import Path
import numpy as np
import soundfile as sf

PROJECT_DIR = Path(__file__).parent
TRAINING_DIR = PROJECT_DIR / "training_bulk"
NBS_SONGS_DIR = PROJECT_DIR / "NBSsongs" / "songs"

def print_header(text):
    print("\n" + "="*70)
    print(f" {text}")
    print("="*70 + "\n")

def create_sample_audio(nbs_name, output_path, duration=60):
    """Create varied sample audio."""
    sr = 44100
    t = np.linspace(0, duration, int(sr * duration))
    
    # Use hash of name for variety
    base_freq = 220 + (hash(nbs_name) % 440)
    
    # Create melody with multiple notes
    audio = np.zeros_like(t)
    for i in range(5):
        freq = base_freq * (1 + i * 0.2)
        note = 0.2 * np.sin(2 * np.pi * freq * t)
        note *= np.sin(np.pi * t / (duration/5))
        audio += note
    
    audio = audio / np.max(np.abs(audio)) * 0.5
    sf.write(str(output_path), audio, sr)

def main():
    print_header("🎵 Bulk NBS Model Trainer")
    
    TRAINING_DIR.mkdir(exist_ok=True)
    
    if not NBS_SONGS_DIR.exists():
        print("NBSsongs not found!")
        return False
    
    # Get all NBS files
    all_nbs = list(NBS_SONGS_DIR.glob("*.nbs"))
    print(f"Found {len(all_nbs)} NBS files")
    
    # Process each
    pairs = 0
    for nbs_file in all_nbs[:50]:  # Limit to 50
        try:
            # Copy NBS
            dest_nbs = TRAINING_DIR / nbs_file.name
            shutil.copy2(nbs_file, dest_nbs)
            
            # Create audio
            audio_path = dest_nbs.with_suffix('.wav')
            if not audio_path.exists():
                create_sample_audio(nbs_file.stem, audio_path)
            
            pairs += 1
            print(f"  ✓ {nbs_file.name}")
        except Exception as e:
            print(f"  ✗ {nbs_file.name}: {e}")
    
    print(f"\nPrepared {pairs} pairs")
    
    # Train
    print_header("Training Model")
    try:
        from musicmp3.nbs_analyzer import learn_audio_model
        result = learn_audio_model(str(TRAINING_DIR))
        
        if result and result.get('model', {}).get('instruments'):
            print(f"\n✅ Trained: {result['songs_analyzed']} songs, {result['notes_extracted']} notes")
            
            # Save profile
            profile = {
                "songs_analyzed": result['songs_analyzed'],
                "total_notes_analyzed": result['notes_extracted'],
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
            
            with open(PROJECT_DIR / "profile.json", 'w') as f:
                json.dump(profile, f, indent=2)
            
            print(f"✅ Profile saved")
            return True
    except Exception as e:
        print(f"✗ Error: {e}")
    
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
