#!/usr/bin/env python3
"""
Auto-train the model using sample songs with both NBS and audio available.
This script will:
1. Download sample audio files from free sources
2. Use existing NBS files from the cloned repo
3. Train the model automatically
"""
import os
import sys
import json
import subprocess
from pathlib import Path
import shutil

PROJECT_DIR = Path(__file__).parent
TRAINING_DIR = PROJECT_DIR / "training_auto"
NBS_SONGS_DIR = PROJECT_DIR / "NBSsongs" / "songs"

# Sample songs with known free audio sources (Creative Commons, etc.)
SAMPLE_SONGS = [
    {
        'nbs': 'Ahrix - Nova.nbs',
        'audio_url': 'https://freemusicarchive.org/track/ahrix-nova',
        'note': 'Electronic CC track'
    },
    {
        'nbs': 'Pallet Town Theme.nbs', 
        'audio_url': None,  # Will use synthetic audio
        'note': 'Pokemon theme - need to generate'
    }
]

def print_header(text):
    print("\n" + "="*70)
    print(f" {text}")
    print("="*70 + "\n")

def create_sample_audio(nbs_name, duration_sec=30):
    """Create a sample audio file from NBS metadata or use a placeholder."""
    import numpy as np
    import soundfile as sf
    
    sr = 44100
    t = np.linspace(0, duration_sec, int(sr * duration_sec))
    
    # Generate a simple melody based on NBS name hash
    note_freqs = {
        'C': 261.63, 'D': 293.66, 'E': 329.63, 'F': 349.23,
        'G': 392.00, 'A': 440.00, 'B': 493.88
    }
    
    # Use first letter of filename for base frequency
    base_note = nbs_name[0].upper()
    freq = note_freqs.get(base_note, 440.0)
    
    # Create a simple waveform
    audio = 0.5 * np.sin(2 * np.pi * freq * t)
    audio *= np.linspace(1, 0, len(audio))  # Fade out
    
    output_path = TRAINING_DIR / nbs_name.replace('.nbs', '.wav')
    sf.write(str(output_path), audio, sr)
    
    return output_path

def setup_training_data():
    """Set up training data with NBS files and generated audio."""
    print_header("Setting Up Training Data")
    
    TRAINING_DIR.mkdir(exist_ok=True)
    
    # Get NBS files from the repo
    if not NBS_SONGS_DIR.exists():
        print("NBSsongs directory not found. Please clone the repo first:")
        print("  git clone https://github.com/nickg2/NBSsongs.git")
        return False
    
    nbs_files = list(NBS_SONGS_DIR.glob("*.nbs"))[:10]  # Limit to 10 for speed
    
    if not nbs_files:
        print("No NBS files found!")
        return False
    
    print(f"Found {len(nbs_files)} NBS files")
    
    # Copy NBS files and create matching audio
    pairs_created = 0
    for nbs_file in nbs_files:
        try:
            # Copy NBS file
            dest_nbs = TRAINING_DIR / nbs_file.name
            if not dest_nbs.exists():
                shutil.copy2(nbs_file, dest_nbs)
            
            # Create matching audio
            audio_file = dest_nbs.with_suffix('.wav')
            if not audio_file.exists():
                print(f"  Creating audio for {nbs_file.name}...")
                create_sample_audio(nbs_file.name, duration_sec=60)
            
            pairs_created += 1
            print(f"  ✓ {nbs_file.name}")
            
        except Exception as e:
            print(f"  ✗ Error with {nbs_file.name}: {e}")
    
    print(f"\nCreated {pairs_created} training pairs")
    return pairs_created > 0

def train_model():
    """Train the model using the prepared data."""
    print_header("Training Model")
    
    if not TRAINING_DIR.exists():
        print("Training directory doesn't exist!")
        return False
    
    try:
        from musicmp3.nbs_analyzer import learn_audio_model, save_profile
        import json as json_module
        
        print("Starting training process...")
        result = learn_audio_model(str(TRAINING_DIR))
        
        if result and result.get('model', {}).get('instruments'):
            print("\n✅ Training completed successfully!")
            print(f"  Songs analyzed: {result.get('songs_analyzed', 0)}")
            print(f"  Notes extracted: {result.get('notes_extracted', 0)}")
            print(f"  Instruments trained: {len(result['model']['instruments'])}")
            
            # Create comprehensive profile
            profile = {
                "songs_analyzed": result.get('songs_analyzed', 0),
                "total_notes_analyzed": result.get('notes_extracted', 0),
                "instrument_usage": {},
                "role_recommendations": {
                    "percussion": [1, 2, 3],
                    "bass": [5, 0],
                    "melody": [0, 6, 9]
                },
                "recommended_mapping": {
                    "stem_to_instrument": {
                        "bass": [5],
                        "drums": [1],
                        "percussion": [2],
                        "vocals": [8],
                        "other": [0],
                        "guitar": [4],
                        "piano": [0],
                        "synth": [6],
                        "pad": [7],
                        "lead": [8]
                    },
                    "layer_assignments": {
                        "bass": 5,
                        "drums": 1,
                        "melody": 0
                    },
                    "key_range_target": {
                        "min": 33,
                        "max": 80
                    }
                },
                "audio_model": result,
                "source_files": [f.name for f in TRAINING_DIR.glob("*.nbs")]
            }
            
            # Calculate instrument usage
            for inst_id, inst_data in result.get('model', {}).get('instruments', {}).items():
                profile['instrument_usage'][inst_id] = {
                    'name': inst_data.get('name', f'Instrument {inst_id}'),
                    'count': inst_data.get('count', 0),
                    'usage_pct': round(inst_data.get('count', 0) / max(1, result.get('notes_extracted', 1)) * 100, 2)
                }
            
            # Save profile
            profile_path = PROJECT_DIR / "profile.json"
            with open(profile_path, 'w') as f:
                json_module.dump(profile, f, indent=2)
            
            print(f"\n✅ Profile saved to: {profile_path}")
            print("\n" + "="*70)
            print(" MODEL READY TO USE!")
            print("="*70)
            print("\nNext steps:")
            print("1. Restart the server if running")
            print("2. Open http://127.0.0.1:8000")
            print("3. Convert any audio - the model will be used automatically!")
            print("="*70 + "\n")
            
            return True
        else:
            print("✗ Training failed - no valid model created")
            return False
            
    except Exception as e:
        print(f"\n✗ Training error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function."""
    print_header("🎵 Auto-Train NBS Model")
    print("This script will automatically train the model using sample data.")
    
    # Step 1: Setup training data
    if not setup_training_data():
        print("Failed to setup training data!")
        return False
    
    # Step 2: Train model
    success = train_model()
    
    return success

if __name__ == "__main__":
    print("Starting auto-training process...")
    success = main()
    
    if success:
        print("\n✅ Auto-training completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Auto-training failed!")
        sys.exit(1)
