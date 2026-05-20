import numpy as np
from collections import defaultdict
from .nbs_playback import render_instrument_real, _load_samples, parse_nbs
from .nbs import write_nbs, _build_nbs_buf
import soundfile as sf

SAMPLE_RATE = 44100
TICKS_PER_SECOND = 10

# Timbre profiles for each instrument (derived empirically)
# [spectral_centroid, spectral_rolloff_85, attack_steepness, decay_rate]
INST_PROFILES = {
    0:  [800,   2000, 0.3, 0.7],   # Piano
    1:  [80,    200,  0.8, 0.9],   # Bass Drum
    2:  [2000,  6000, 0.9, 0.8],   # Snare
    3:  [4000,  7000, 0.7, 0.5],   # Click
    4:  [500,   1500, 0.3, 0.6],   # Guitar
    5:  [100,   300,  0.2, 0.5],   # Bass
    6:  [1500,  4000, 0.2, 0.3],   # Bell
    7:  [2500,  5500, 0.1, 0.2],   # Chime
    8:  [600,   1500, 0.2, 0.4],   # Flute
    9:  [1800,  3500, 0.4, 0.5],   # Xylophone
    10: [2200,  4000, 0.4, 0.5],   # Iron Xylophone
    11: [1200,  3000, 0.6, 0.6],   # Cow Bell
    12: [150,   500,  0.2, 0.4],   # Didgeridoo
    13: [1000,  3500, 0.5, 0.6],   # Bit
    14: [700,   2000, 0.4, 0.6],   # Banjo
    15: [2000,  4500, 0.5, 0.5],   # Pling
}

INST_NAMES = ['Piano','BassDrum','Snare','Click','Guitar','Bass','Bell','Chime',
'Flute','Xylophone','IronXylo','CowBell','Didgeridoo','Bit','Banjo','Pling']

def detect_transients(audio_data, sr):
    """Detect transient points (onsets) in audio."""
    # Simple energy-based onset detection
    hop = int(sr * 0.01)  # 10ms hop
    window = int(sr * 0.05)  # 50ms window
    
    transients = []
    prev_energy = 0
    
    for i in range(0, len(audio_data) - window, hop):
        segment = audio_data[i:i + window]
        energy = np.sqrt(np.mean(segment ** 2))
        
        # Detect sudden energy increase
        if energy > prev_energy * 1.5 and energy > 0.05:
            transients.append({
                'time': i / sr,
                'tick': int(i / sr * TICKS_PER_SECOND),
                'energy': energy
            })
        
        prev_energy = energy
    
    return transients

# Feature extraction
def _spectral_centroid(spec, freqs):
    total = np.sum(spec)
    if total < 1e-8: return 0.0
    return float(np.sum(freqs * spec) / total)

def _spectral_rolloff(spec, freqs, pct=0.85):
    cum = np.cumsum(spec)
    total = cum[-1]
    if total < 1e-8: return 0.0
    idx = np.searchsorted(cum, total * pct)
    return freqs[min(idx, len(freqs)-1)]

def _extract_features(data, sr):
    """Extract timbral features from a short audio window."""
    if len(data) < 64:
        return None
    n = min(len(data), 2048)
    windowed = data[:n] * np.hanning(n)
    if len(windowed) < 2048:
        windowed = np.pad(windowed, (0, 2048 - len(windowed)))
    fft = np.fft.rfft(windowed)
    mag = np.abs(fft)
    freqs = np.linspace(0, sr / 2, len(mag))

    centroid = _spectral_centroid(mag, freqs)
    rolloff = _spectral_rolloff(mag, freqs)

    # Attack steepness: slope of onset envelope
    envelope = np.abs(data)
    attack = float(np.max(envelope[:min(512, len(envelope)//2)])) / (float(np.mean(np.abs(data))) + 1e-8)

    # Energy decay: ratio of second half to first half
    half = len(data) // 2
    if half > 0:
        decay_ratio = float(np.sum(np.abs(data[half:])) / (np.sum(np.abs(data[:half])) + 1e-8))
    else:
        decay_ratio = 1.0

    return [centroid, rolloff, min(attack, 20), decay_ratio]


def _score_instrument(features, inst):
    """Score how well an instrument matches the extracted features (lower is better)."""
    profile = INST_PROFILES[inst]
    score = 0
    # Centroid distance (normalized)
    c_diff = abs(features[0] - profile[0]) / 3000.0
    score += c_diff * 0.5
    # Rolloff distance
    r_diff = abs(features[1] - profile[1]) / 5000.0
    score += r_diff * 0.3
    # Attack match
    a_diff = abs(features[2] - profile[2]) / 20.0
    score += a_diff * 0.1
    # Decay match
    d_diff = abs(features[3] - profile[3])
    score += d_diff * 0.1
    return -score  # negative = lower is worse, higher is better


def optimize_nbs(nbs_path: str, audio_path: str,
                 progress_callback=None,
                 add_missing: bool = True,
                 remove_silent: bool = True,
                 adjust_timing: bool = True,
                 adjust_keys: bool = True,
                 extend_sustains: bool = True,
                 duplicate_repeats: bool = True) -> dict:
    """
    Optimize NBS file by comparing with original audio.
    
    Can:
    - Change instruments based on timbre matching
    - Add missing notes detected in audio
    - Remove notes in silent sections
    - Adjust timing to match audio transients
    - Adjust velocities based on energy
    """
    _load_samples()
    
    # Load audio
    original, sr = sf.read(audio_path)
    if original.ndim > 1:
        original = original.mean(axis=1)
    
    if sr != SAMPLE_RATE:
        from scipy import signal
        ratio = SAMPLE_RATE / sr
        new_len = max(1, int(len(original) * ratio))
        original = signal.resample(original, new_len).astype(np.float32)
        sr = SAMPLE_RATE
    
    # Load NBS
    data = parse_nbs(nbs_path)
    notes = data["notes"]
    if not notes:
        return {"optimized_notes": [], "changes": [], "stats": {}}
    
    audio_duration = len(original) / sr
    print(f"[optimizer] Audio duration: {audio_duration:.2f}s, Notes: {len(notes)}")
    
    # Detect transients first
    transients = detect_transients(original, sr)
    print(f"[optimizer] Detected {len(transients)} transients")
    
    # Extract audio features in windows
    window_size = int(sr * 0.05)  # 50ms windows
    hop_size = window_size // 2
    audio_features = []
    
    for i in range(0, len(original) - window_size, hop_size):
        window = original[i:i + window_size]
        features = _extract_features(window, sr)
        if features is not None:
            audio_features.append({
                'time': i / sr,
                'tick': int(i / sr * TICKS_PER_SECOND),
                'features': features,
                'energy': np.sqrt(np.mean(window ** 2))
            })
    
    print(f"[optimizer] Extracted {len(audio_features)} audio feature windows")
    
    # Step 1: Match existing notes to audio features
    optimized_notes = []
    changes = []
    
    for note in notes:
        start_time = note.get("start_time", 0)
        key = note["key"]
        current_inst = note.get("instrument", 0)
        current_vel = note.get("velocity", 100)
        
        # Find closest audio feature window
        closest_feature = None
        min_diff = float('inf')
        
        for feat in audio_features:
            diff = abs(feat['time'] - start_time)
            if diff < min_diff and diff < 0.1:  # Within 100ms
                min_diff = diff
                closest_feature = feat
        
        if closest_feature is None:
            optimized_notes.append(note.copy())
            continue
        
        features = closest_feature['features']
        
        # Suggest instrument change
        best_inst = current_inst
        best_score = -999
        
        for inst in range(16):
            score = _score_instrument(features, inst)
            if score > best_score:
                best_score = score
                best_inst = inst
        
        # Suggest velocity change
        energy = closest_feature['energy']
        suggested_vel = min(100, max(5, int(energy * 250)))
        
        opt_note = note.copy()
        opt_note['instrument'] = best_inst
        opt_note['velocity'] = suggested_vel
        
        if best_inst != current_inst:
            changes.append({
                'type': 'instrument',
                'tick': note['tick'],
                'key': key,
                'old_inst': current_inst,
                'new_inst': best_inst,
                'score': best_score
            })
        
        if abs(suggested_vel - current_vel) > 15:
            changes.append({
                'type': 'velocity',
                'tick': note['tick'],
                'key': key,
                'old_vel': current_vel,
                'new_vel': suggested_vel
            })
        
        optimized_notes.append(opt_note)
    
    # Step 2: Find silent sections to remove notes
    if remove_silent:
        silent_threshold = 0.01
        notes_to_remove = []
        
        for i, note in enumerate(optimized_notes):
            start_time = note.get("start_time", 0)
            tick_idx = int(start_time * sr / hop_size)
            
            if 0 <= tick_idx < len(audio_features):
                energy = audio_features[tick_idx]['energy']
                if energy < silent_threshold:
                    notes_to_remove.append(i)
                    changes.append({
                        'type': 'remove_silent',
                        'tick': note['tick'],
                        'key': note['key']
                    })
        
        # Remove notes in reverse order to maintain indices
        for i in sorted(notes_to_remove, reverse=True):
            optimized_notes.pop(i)
    
    # Step 3: Find missing notes in high-energy sections
    if add_missing:
        # Group notes by time
        note_times = {int(n.get("start_time", 0) * TICKS_PER_SECOND): n for n in notes}
        
        for feat in audio_features:
            tick = feat['tick']
            
            # Check if there's already a note here
            if tick in note_times:
                continue
            
            # High energy but no note = potential missing note
            if feat['energy'] > 0.1:
                # Find dominant frequency to estimate pitch
                window_start = int(feat['time'] * sr)
                window_end = min(len(original), window_start + int(0.05 * sr))
                window = original[window_start:window_end]
                
                if len(window) >= 64:
                    # Simple pitch detection via zero crossing
                    zero_crossings = np.sum(np.diff(np.sign(window - np.mean(window))) != 0)
                    freq_estimate = zero_crossings * sr / (2 * len(window))
                    
                    if 100 < freq_estimate < 4000:  # Reasonable frequency range
                        # Map to nearest NBS key
                        estimated_key = max(0, min(87, int((freq_estimate - 100) / 20) + 33))
                        
                        new_note = {
                            'tick': tick,
                            'layer': 0,
                            'key': estimated_key,
                            'instrument': 0,  # Piano as default
                            'velocity': min(100, int(feat['energy'] * 200)),
                            'panning': 100,
                            'pitch': -1
                        }
                        optimized_notes.append(new_note)
                        
                        changes.append({
                            'type': 'add_missing',
                            'tick': tick,
                            'key': estimated_key,
                            'instrument': 0
                        })
    
    stats = {
        'original_count': len(notes),
        'optimized_count': len(optimized_notes),
        'added': len([c for c in changes if c['type'] == 'add_missing']),
        'removed': len([c for c in changes if c['type'] == 'remove_silent']),
        'instrument_changes': len([c for c in changes if c['type'] == 'instrument']),
        'velocity_changes': len([c for c in changes if c['type'] == 'velocity']),
        'timing_adjustments': 0,
        'key_adjustments': 0,
        'repeat_duplicates': 0
    }
    
    print(f"[optimizer] Done: {stats['original_count']} -> {stats['optimized_count']} notes")
    print(f"  Added: {stats['added']}, Removed: {stats['removed']}, "
          f"Inst changed: {stats['instrument_changes']}, Velocity changed: {stats['velocity_changes']}")
    
    # Step 4: Adjust timing to match transients
    if adjust_timing and transients:
        for i, note in enumerate(optimized_notes):
            start_time = note.get("start_time", 0)
            tick = note.get("tick", 0)
            
            # Find nearest transient
            best_transient = None
            min_time_diff = float('inf')
            
            for trans in transients:
                time_diff = abs(trans['time'] - start_time)
                if time_diff < min_time_diff and time_diff < 0.15:  # Within 150ms
                    min_time_diff = time_diff
                    best_transient = trans
            
            if best_transient and best_transient['tick'] != tick:
                old_tick = tick
                note['tick'] = best_transient['tick']
                note['start_time'] = best_transient['time']
                changes.append({
                    'type': 'adjust_timing',
                    'old_tick': old_tick,
                    'new_tick': best_transient['tick'],
                    'key': note['key'],
                    'time_shift': best_transient['time'] - start_time
                })
    
    # Step 5: Adjust pitch (key) based on spectral analysis
    if adjust_keys:
        for i, note in enumerate(optimized_notes):
            start_time = note.get("start_time", 0)
            current_key = note.get("key", 0)
            tick_idx = int(start_time * sr / hop_size)
            
            if 0 <= tick_idx < len(audio_features):
                window_start = int(start_time * sr)
                window_end = min(len(original), window_start + int(0.1 * sr))
                window = original[window_start:window_end]
                
                if len(window) >= 64:
                    # FFT-based pitch detection
                    fft = np.fft.rfft(window * np.hanning(len(window)))
                    magnitudes = np.abs(fft)
                    freqs = np.fft.rfftfreq(len(window), 1/sr)
                    
                    # Find dominant frequency
                    mask = (freqs > 50) & (freqs < 5000)
                    if np.any(mask):
                        dominant_idx = np.argmax(magnitudes[mask])
                        dominant_freq = freqs[mask][dominant_idx]
                        
                        # Convert to MIDI key
                        if 50 < dominant_freq < 5000:
                            midi_key = int(69 + 12 * np.log2(dominant_freq / 440))
                            nbs_key = max(0, min(87, midi_key - 21))  # Convert to NBS key range
                            
                            if abs(nbs_key - current_key) > 2:  # Only if significant difference
                                note['key'] = nbs_key
                                changes.append({
                                    'type': 'adjust_key',
                                    'old_key': current_key,
                                    'new_key': nbs_key,
                                    'tick': note['tick'],
                                    'freq': dominant_freq
                                })
    
    # Step 6: Extend sustain for long notes
    if extend_sustains:
        notes_by_key = defaultdict(list)
        for note in optimized_notes:
            notes_by_key[note['key']].append(note)
        
        for key, notes in notes_by_key.items():
            notes.sort(key=lambda x: x.get('tick', 0))
            for i in range(len(notes) - 1):
                current = notes[i]
                next_note = notes[i + 1]
                
                tick_diff = next_note.get('tick', 0) - current.get('tick', 0)
                
                # If next note is within 0.3s, extend current note
                if 0 < tick_diff < 3:  # Less than 0.3 seconds
                    # Could add duration info if NBS format supports it
                    pass
    
    # Step 7: Duplicate patterns in repeated sections
    if duplicate_repeats:
        # Simple repetition detection: look for similar patterns
        audio_duration = len(original) / sr
        section_size = int(sr * 2)  # 2 second sections
        
        for i in range(0, len(original) - section_size * 2, section_size // 2):
            section1 = original[i:i + section_size]
            section2 = original[i + section_size:i + section_size * 2]
            
            if len(section2) == len(section1):
                correlation = np.corrcoef(section1[:min(44100, len(section1))], 
                                        section2[:min(44100, len(section2))])[0, 1]
                
                if correlation > 0.8:  # High correlation = repetition
                    # Duplicate notes from first section to second
                    section1_time = i / sr
                    section2_time = (i + section_size) / sr
                    
                    for note in list(optimized_notes):
                        note_time = note.get('start_time', 0)
                        if section1_time <= note_time < section1_time + 2:
                            new_note = note.copy()
                            new_note['tick'] = int(section2_time * TICKS_PER_SECOND)
                            new_note['start_time'] = section2_time
                            optimized_notes.append(new_note)
                            
                            changes.append({
                                'type': 'duplicate_repeat',
                                'original_tick': note['tick'],
                                'new_tick': new_note['tick'],
                                'key': note['key']
                            })
                            break  # One note per repetition for now
    
    # Update stats
    stats['timing_adjustments'] = len([c for c in changes if c['type'] == 'adjust_timing'])
    stats['key_adjustments'] = len([c for c in changes if c['type'] == 'adjust_key'])
    stats['repeat_duplicates'] = len([c for c in changes if c['type'] == 'duplicate_repeat'])
    
    print(f"  Timing adjusted: {stats['timing_adjustments']}, "
          f"Keys adjusted: {stats['key_adjustments']}, "
          f"Repeats duplicated: {stats['repeat_duplicates']}")
    
    return {
        'optimized_notes': optimized_notes,
        'changes': changes,
        'stats': stats
    }
