#!/usr/bin/env python3
"""Download and train with 20 more popular songs."""
import os, sys, subprocess, shutil, json
from pathlib import Path

TRAINING_DIR = Path.home() / ".musicmp3" / "training"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)

# 20 popular songs that definitely exist on YouTube
SONGS = [
    ("bad_apple", "Bad Apple!! Touhou piano cover"),
    ("believer", "Imagine Dragons Believer official"),
    ("bohemian_rhapsody", "Queen Bohemian Rhapsody official"),
    ("teto_birdbrain", "Teto Birdbrain vocaloid"),
    ("axel_f", "Crazy Frog Axel F original"),
    ("pallet_town", "Pokemon Pallet Town theme"),
    ("moonlight_sonata", "Beethoven Moonlight Sonata 3rd movement"),
    ("take_on_me", "A-ha Take On Me official"),
    ("never_gonna_give_up", "Rick Astley Never Gonna Give You Up"),
    ("despacito", "Luis Fonsi Despacito official"),
    ("clocks", "Coldplay Clocks official"),
    ("fireflies", "Owl City Fireflies official"),
    ("still_alive", "Portal Still Alive Jonathan Coulton"),
    ("linus_lucy", "Linus and Lucy Vince Guaraldi"),
    ("sweater_weather", "Neighbour Sweater Weather official"),
    ("sweet_child_o_mine", "Guns N Roses Sweet Child O Mine"),
    ("through_fire_flames", "DragonForce Through the Fire and Flames"),
    ("dixie_land", "Dixie Land jazz standard"),
    ("omfg_i_love_you", "OMFG I Love You official"),
    ("peanuts_theme", "Peanuts theme Linus and Lucy"),
    ("fellowship_ring", "Lord of the Rings Fellowship theme"),
    ("sleigh_ride", "Sleigh Ride Christmas classic"),
    ("thousand_miles", "Vanessa Carlton A Thousand Miles"),
    ("all_i_want_christmas", "Mariah Carey All I Want for Christmas"),
]

def print_header(text):
    print(f"\n{'='*70}\n {text}\n{'='*70}\n")

def download_audio(search_query, output_name):
    """Download audio from YouTube."""
    try:
        output_path = TRAINING_DIR / f"{output_name}.mp3"
        if output_path.exists():
            print(f"  ✓ Already exists: {output_name}")
            return output_path
        
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
        
        print(f"  Downloading: {search_query[:50]}...")
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
    print_header("🎵 Training with 20+ More Songs")
    
    # Get NBS files from repo
    nbs_dir = Path("NBSsongs/songs")
    if not nbs_dir.exists():
        print("NBSsongs directory not found!")
        return False
    
    all_nbs = list(nbs_dir.glob("*.nbs"))
    print(f"Found {len(all_nbs)} NBS files in repo")
    
    # Match and download
    pairs_created = 0
    
    for nbs_file in all_nbs:
        nbs_name = nbs_file.stem.lower().replace(" ", "_").replace("-", "_")
        
        # Find matching song in our list
        matched = False
        for song_id, search_query in SONGS:
            if song_id in nbs_name or nbs_name in song_id:
                # Copy NBS
                dest_nbs = TRAINING_DIR / nbs_file.name
                if not dest_nbs.exists():
                    shutil.copy2(nbs_file, dest_nbs)
                
                # Download audio
                audio_path = download_audio(search_query, nbs_file.stem)
                
                if audio_path:
                    pairs_created += 1
                    print(f"  ✓ Pair: {nbs_file.name}")
                    matched = True
                break
        
        if not matched and pairs_created < 24:  # Limit total
            # Try to use any NBS with downloaded audio
            dest_nbs = TRAINING_DIR / nbs_file.name
            if not dest_nbs.exists():
                shutil.copy2(nbs_file, dest_nbs)
            
            # Download generic audio
            audio_path = download_audio(f"{nbs_file.stem} piano cover", nbs_file.stem)
            if audio_path:
                pairs_created += 1
                print(f"  ✓ Generic: {nbs_file.name}")
    
    print(f"\n✅ Created {pairs_created} training pairs")
    
    # Train
    print_header("Training Model")
    try:
        from musicmp3.nbs_analyzer import learn_audio_model
        
        result = learn_audio_model(str(TRAINING_DIR))
        
        if result and result.get('model', {}).get('instruments'):
            print(f"\n✅ Training completed!")
            print(f"  Songs: {result.get('songs_analyzed', 0)}")
            print(f"  Notes: {result.get('notes_extracted', 0):,}")
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
            
            profile_path = Path("profile.json")
            with open(profile_path, 'w') as f:
                json.dump(profile, f, indent=2)
            
            print(f"\n✅ Profile saved")
            print("\n" + "="*70)
            print("MODEL READY! Refresh the web page to see results.")
            print("="*70)
            return True
            
    except Exception as e:
        print(f"\n✗ Training error: {e}")
        import traceback
        traceback.print_exc()
    
    return False

if __name__ == "__main__":
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, timeout=5)
    except:
        print("Installing yt-dlp...")
        subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"])
    
    success = main()
    sys.exit(0 if success else 1)
