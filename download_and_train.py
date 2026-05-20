#!/usr/bin/env python3
"""
Download NBS songs from GitHub repo and train the model automatically.
"""
import os
import sys
import json
import subprocess
from pathlib import Path
from urllib.request import urlretrieve
import requests

PROJECT_DIR = Path(__file__).parent
NBS_REPO_URL = "https://raw.githubusercontent.com/nickg2/NBSsongs/master"
TRAINING_DIR = PROJECT_DIR / "training_data"
NBS_SONGS_DIR = PROJECT_DIR / "NBSsongs"

def print_header(text):
    print("\n" + "="*60)
    print(f" {text}")
    print("="*60 + "\n")

def scan_nbs_files(directory):
    """Scan directory for NBS files."""
    nbs_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.nbs'):
                nbs_files.append(Path(root) / file)
    return nbs_files

def download_file(url, output_path):
    """Download a file from URL."""
    try:
        print(f"  Downloading: {url}")
        urlretrieve(url, output_path)
        return True
    except Exception as e:
        print(f"  Error downloading: {e}")
        return False

def get_nbs_list_from_github():
    """Get list of NBS files from GitHub repo."""
    print_header("Getting NBS file list from GitHub...")
    
    # Use GitHub API to get file list
    api_url = "https://api.github.com/repos/nickg2/NBSsongs/git/trees/master?recursive=1"
    
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            nbs_files = [f['path'] for f in data['tree'] if f['path'].endswith('.nbs')]
            print(f"Found {len(nbs_files)} NBS files in repository")
            return nbs_files
    except Exception as e:
        print(f"Error getting file list: {e}")
    
    return []

def download_nbs_songs():
    """Download NBS songs from GitHub."""
    print_header("Downloading NBS Songs")
    
    # Clone or update the repository
    if NBS_SONGS_DIR.exists():
        print("Repository already exists, updating...")
        subprocess.run(['git', '-C', str(NBS_SONGS_DIR), 'pull'], check=True)
    else:
        print("Cloning repository...")
        subprocess.run(['git', 'clone', 'https://github.com/nickg2/NBSsongs.git', str(NBS_SONGS_DIR)], check=True)
    
    # Scan for NBS files
    nbs_files = scan_nbs_files(NBS_SONGS_DIR)
    print(f"Found {len(nbs_files)} NBS files locally")
    
    return nbs_files

def prepare_training_data():
    """Prepare training data by copying NBS files to training directory."""
    print_header("Preparing Training Data")
    
    TRAINING_DIR.mkdir(exist_ok=True)
    
    # Copy NBS files to training directory
    nbs_files = scan_nbs_files(NBS_SONGS_DIR)
    
    if not nbs_files:
        print("No NBS files found!")
        return []
    
    # Create symlinks or copy files
    for nbs_path in nbs_files[:20]:  # Limit to first 20 for testing
        dest_path = TRAINING_DIR / nbs_path.name
        if not dest_path.exists():
            try:
                # Try to create symlink first
                if not dest_path.is_symlink():
                    dest_path.symlink_to(nbs_path)
                print(f"  ✓ {nbs_path.name}")
            except Exception as e:
                # If symlink fails, copy the file
                import shutil
                shutil.copy2(nbs_path, dest_path)
                print(f"  ✓ {nbs_path.name} (copied)")
    
    return list(TRAINING_DIR.glob("*.nbs"))

def train_model():
    """Train the model using the prepared data."""
    print_header("Training Model")
    
    if not TRAINING_DIR.exists():
        print("Training directory doesn't exist!")
        return False
    
    # Import and use the training functions
    sys.path.insert(0, str(PROJECT_DIR))
    
    try:
        from musicmp3.nbs_analyzer import learn_audio_model, save_profile
        from musicmp3.server import PROFILE_PATH
        import json
        
        print("Starting training...")
        result = learn_audio_model(str(TRAINING_DIR))
        
        if result:
            print("\n✓ Training completed successfully!")
            print(f"  Songs analyzed: {result.get('songs_analyzed', 0)}")
            print(f"  Notes extracted: {result.get('notes_extracted', 0)}")
            print(f"  Instruments trained: {len(result.get('model', {}).get('instruments', {}))}")
            
            # Save profile
            profile = {
                "songs_analyzed": result.get('songs_analyzed', 0),
                "total_notes_analyzed": result.get('notes_extracted', 0),
                "instrument_usage": {},
                "role_recommendations": {},
                "recommended_mapping": {},
                "audio_model": result,
                "source_files": [str(f.name) for f in TRAINING_DIR.glob("*.nbs")]
            }
            
            PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(PROFILE_PATH, 'w') as f:
                json.dump(profile, f, indent=2)
            print(f"\n✓ Profile saved to {PROFILE_PATH}")
            
            return True
        else:
            print("✗ Training failed - no result")
            return False
            
    except Exception as e:
        print(f"✗ Training error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function."""
    print_header("🎵 NBS Downloader & Trainer")
    
    # Step 1: Download NBS songs
    nbs_files = download_nbs_songs()
    
    if not nbs_files:
        print("No NBS files found or downloaded!")
        return False
    
    # Step 2: Prepare training data
    training_files = prepare_training_data()
    
    if not training_files:
        print("No training files prepared!")
        return False
    
    # Step 3: Train model
    success = train_model()
    
    if success:
        print_header("✅ Training Complete!")
        print("\nNext steps:")
        print("1. Open the web interface: http://127.0.0.1:8000")
        print("2. Go to '🧠 Entrenar modelo'")
        print("3. Click '🔄 Reentrenar' to use the new model")
        print("\nThe model is now ready to use!")
        return True
    else:
        print_header("❌ Training Failed")
        return False

if __name__ == "__main__":
    # Install required packages
    try:
        import requests
    except ImportError:
        print("Installing required packages...")
        subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
        import requests
    
    success = main()
    sys.exit(0 if success else 1)
