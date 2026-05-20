// Main app logic
const $ = id => document.getElementById(id);

// Safe event listener helper
function safeAddEventListener(id, event, handler) {
  const el = $(id);
  if (el) {
    el.addEventListener(event, handler);
    return true;
  }
  console.warn(`Element #${id} not found, skipping event listener`);
  return false;
}

const INST_NAMES = ['Piano','BassDrum','Snare','Click','Bass','Flute','Bell','Chime',
'Flute','Xylophone','IronXylo','CowBell','Didgeridoo','Bit','Banjo','Pling'];
const INST_COLORS = ['#e74c3c','#3498db','#2ecc71','#f1c40f','#9b59b6','#1abc9c','#e67e22','#34495e','#16a085','#c0392b','#2980b9','#27ae60','#f39c12','#8e44ad','#d35400','#7f8c8d'];

let sessionId = null;
let noteData = [];
let pianoRoll;
let tempo_bps = 10;
let currentNbsFile = null;

// Init
async function init() {
  console.log('init() started');
  
  const canvas = $('piano-roll');
  if (!canvas) {
    console.error('Canvas element not found!');
  } else {
    console.log('Canvas found, initializing PianoRoll');
    pianoRoll = new PianoRoll(canvas);
    pianoRoll.onSelect = onNoteSelect;
    pianoRoll.onChange = onNotesChanged;
  }

    // Populate instrument dropdown
    const sel = $('prop-inst');
    INST_NAMES.forEach((name, i) => {
        const opt = document.createElement('option');
        opt.value = i;
        opt.textContent = `${i} ${name}`;
        sel.appendChild(opt);
    });

    // Build legend
    $('inst-legend').innerHTML = INST_NAMES.map((n, i) =>
        `<span><span class="inst-dot" style="background:${INST_COLORS[i]}"></span>${i} ${n}</span>`
    ).join(' | ');

// Create session
try {
  const s = await API.createSession();
  sessionId = s.session_id;
  setStatus('Ready — cargá un NBS o convertí un audio');
} catch(e) {
  setStatus('Error: ' + e.message);
}

// Events - NBS upload
safeAddEventListener('input-nbs', 'change', onNbsUpload);
safeAddEventListener('btn-render-upload', 'click', onRenderFromUpload);

// Events - Convert
safeAddEventListener('btn-convert', 'click', onConvert);
safeAddEventListener('btn-render', 'click', onRender);
safeAddEventListener('btn-interactive-roll', 'click', onInteractiveRoll);
safeAddEventListener('btn-optimize', 'click', onOptimize);
safeAddEventListener('btn-save-note', 'click', onSaveNote);
safeAddEventListener('btn-add-note', 'click', onAddNote);
safeAddEventListener('btn-delete-note', 'click', onDeleteNote);
safeAddEventListener('btn-sync-table', 'click', onSyncTable);
safeAddEventListener('btn-download', 'click', onDownload);

// Zoom
safeAddEventListener('btn-zoom-in', 'click', () => {
  pianoRoll.zoom = Math.min(10, pianoRoll.zoom * 1.3);
  pianoRoll.viewStart = pianoRoll.viewStart + pianoRoll._visibleTicks() / 4;
  pianoRoll._constrainView();
  pianoRoll.draw();
  const el = $('zoom-info');
  if (el) el.textContent = `Zoom: ${pianoRoll.zoom.toFixed(1)}x`;
});
safeAddEventListener('btn-zoom-out', 'click', () => {
  pianoRoll.zoom = Math.max(0.2, pianoRoll.zoom / 1.3);
  pianoRoll.viewStart = pianoRoll.viewStart - pianoRoll._visibleTicks() / 4;
  pianoRoll._constrainView();
  pianoRoll.draw();
  const el = $('zoom-info');
  if (el) el.textContent = `Zoom: ${pianoRoll.zoom.toFixed(1)}x`;
});

// Audio playback
safeAddEventListener('audio-player', 'timeupdate', () => {
  const audio = $('audio-player');
  if (!audio || !audio.src) return;
  const tick = audio.currentTime * tempo_bps;
  pianoRoll.setPlaybackTick(tick);
});
safeAddEventListener('audio-player', 'ended', () => {
  pianoRoll.setPlaybackTick(-1);
  pianoRoll.draw();
});

// Sliders
['low', 'high', 'transpose'].forEach(id => {
  const sl = $(`slider-${id}`);
  const val = $(`val-${id}`);
  if (sl && val) {
    sl.addEventListener('input', () => val.textContent = sl.value);
  }
});

safeAddEventListener('prop-vel', 'input', () => {
  const val = $('val-vel');
  const prop = $('prop-vel');
  if (val && prop) val.textContent = prop.value;
});
safeAddEventListener('prop-pan', 'input', () => {
  const val = $('val-pan');
  const prop = $('prop-pan');
  if (val && prop) val.textContent = prop.value;
});

// Training
safeAddEventListener('btn-upload-pair', 'click', onUploadPair);
safeAddEventListener('btn-relearn', 'click', onRelearn);
safeAddEventListener('btn-gen-profile', 'click', onGenProfile);

    // File inputs
    $('input-file').addEventListener('change', () => {
        if ($('input-file').files.length) $('input-query').value = '';
    });
    $('input-query').addEventListener('input', () => {
        if ($('input-query').value) $('input-file').value = '';
    });
}

// === Cargar NBS ===

async function onNbsUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  try {
    console.log('1. Starting upload of:', file.name);
    setStatus(`Cargando ${file.name}...`);

    // Step 1: Upload file
    const sessionData = await API.uploadNbs(file, sessionId);
    console.log('2. Upload complete:', sessionData);

    // Step 2: Get notes data
    const notesData = await API.getNotes(sessionId);
    console.log('3. Notes data received:', notesData);
    
    noteData = notesData.notes || [];
    tempo_bps = notesData.tempo_bps || 10;
    console.log('4. Notes loaded:', noteData.length);

    // Step 3: Show info
    const nbsInfo = $('nbs-info');
    if (nbsInfo) {
      nbsInfo.style.display = 'block';
    }
    
    const nbsName = $('nbs-name');
    if (nbsName) {
      nbsName.textContent = file.name;
    }
    
    const nbsStats = $('nbs-stats');
    if (nbsStats) {
      nbsStats.textContent = `${noteData.length} notas, ${notesData.max_layer || 1} capas`;
    }

    // Step 4: Render piano roll
    if (pianoRoll && noteData.length > 0) {
      console.log('5. Rendering piano roll with', noteData.length, 'notes');
      pianoRoll.setNotes(noteData);
      pianoRoll.draw();
    } else if (!pianoRoll) {
      console.error('pianoRoll not initialized');
    } else if (noteData.length === 0) {
      console.warn('No notes to render');
    }
    
    // Step 5: Update UI
    updateNoteCount();
    updateTable();

    // Step 6: Enable render button
    const renderUploadBtn = $('btn-render-upload');
    if (renderUploadBtn) {
      renderUploadBtn.disabled = false;
      renderUploadBtn.textContent = `🔊 Renderizar: ${file.name}`;
    }
    
    currentNbsFile = file;

    setStatus(`✓ ${file.name} cargado (${noteData.length} notas). Click en "Renderizar Audio"`);
  } catch(err) {
    console.error('Error in onNbsUpload:', err);
    console.error('Stack:', err.stack);
    setStatus('Error: ' + err.message);
  }
}

// Render from upload button
async function onRenderFromUpload() {
  console.log('Render button clicked');
  console.log('currentNbsFile:', currentNbsFile);
  console.log('sessionId:', sessionId);
  
  if (!currentNbsFile) {
    setStatus('Primero cargá un archivo .nbs');
    return;
  }
  
  if (!sessionId) {
    setStatus('Error: No hay sesión activa');
    return;
  }

  try {
    setStatus('Renderizando audio...');
    console.log('Calling API.render...');
    
    const result = await API.render(sessionId);
    console.log('Render result:', result);
    
    const audio = $('audio-player');
    if (audio && result.wav) {
      console.log('Setting audio src:', result.wav);
      audio.src = result.wav + '?t=' + Date.now();
      audio.load();
      nbsStats.textContent = `${noteData.length} notas, ${notesData.max_layer || 1} capas`;
    }

    // Step 4: Render piano roll
    if (pianoRoll && noteData.length > 0) {
      console.log('5. Rendering piano roll with', noteData.length, 'notes');
      pianoRoll.setNotes(noteData);
      pianoRoll.draw();
    } else if (!pianoRoll) {
      console.error('pianoRoll not initialized');
    } else if (noteData.length === 0) {
      console.warn('No notes to render');
    }
    
    // Step 5: Update UI
    updateNoteCount();
    updateTable();

    // Step 6: Enable buttons
    const renderBtn = $('btn-render');
    const downloadNbsBtn = $('btn-download-nbs');
    const syncTableBtn = $('btn-sync-table');
    
    if (renderBtn) renderBtn.disabled = false;
    if (downloadNbsBtn) downloadNbsBtn.disabled = false;
    if (syncTableBtn) syncTableBtn.disabled = false;

    setStatus(`✓ ${file.name} cargado (${noteData.length} notas)`);
  } catch(err) {
    console.error('Error in onNbsUpload:', err);
    console.error('Stack:', err.stack);
    setStatus('Error: ' + err.message);
  }
}

async function onConvert() {
    const query = $('input-query').value;
    const file = $('input-file').files[0];
    const mode = $('input-mode').value;
    const low = parseInt($('slider-low').value);
    const high = parseInt($('slider-high').value);
    const transpose = parseInt($('slider-transpose').value);

    if (!query && !file) {
        setStatus('Ingresá un nombre o subí un archivo');
        return;
    }

    try {
        setStatus(query ? `Buscando "${query}"...` : `Convirtiendo ${file.name}...`);
        $('btn-convert').disabled = true;

        const result = await API.convert(sessionId, {
            query: query,
            file: file,
            mode: mode,
            target_low: low,
            target_high: high,
            transpose: transpose
        });
        
        const notesData = await API.getNotes(sessionId);
        noteData = notesData.notes;
        tempo_bps = notesData.tempo_bps || 10;
        
        pianoRoll.setNotes(noteData);
        pianoRoll.draw();
        updateNoteCount();
        updateStats(noteData);
        updateTable();
        
$('btn-render').disabled = false;
$('btn-interactive-roll').disabled = false;
$('btn-optimize').disabled = false;
$('btn-download-nbs').disabled = false;
$('btn-sync-table').disabled = false;
        
        setStatus(`✓ Convertido: ${noteData.length} notas`);
        $('btn-convert').disabled = false;
    } catch(err) {
        setStatus('Error: ' + err.message);
        $('btn-convert').disabled = false;
    }
}

async function onRender() {
  try {
    setStatus('Renderizando audio...');
    const result = await API.render(sessionId);

    const audio = $('audio-player');
    audio.src = result.wav + '?t=' + Date.now();
    audio.load();

    if (result.piano_roll) {
      // Piano roll ya está renderizado
    }

    $('btn-download-wav').disabled = false;
    $('btn-interactive-roll').disabled = false;
    $('audio-info').style.display = 'block';

    // Auto-play
    await audio.play();
    setStatus('✓ Audio listo');
  } catch(err) {
    setStatus('Error render: ' + err.message);
  }
}

async function onInteractiveRoll() {
  try {
    setStatus('Generando piano roll interactivo...');
    window.open(`/api/session/${sessionId}/piano_roll_html`, '_blank');
    setStatus('✓ Piano roll interactivo abierto');
  } catch(err) {
    setStatus('Error: ' + err.message);
  }
}

async function onOptimize() {
  try {
    $('btn-optimize').disabled = true;
    setStatus('Optimizando NBS...');
    
    const result = await API.optimize(sessionId);
    
    // Reload notes
    noteData = await API.getNotes(sessionId).then(d => d.notes);
    pianoRoll.setNotes(noteData);
    pianoRoll.draw();
    updateNoteCount();
    updateStats(noteData);
    updateTable();
    
    const stats = result.stats || {};
    const parts = [];
    
    if (stats.added > 0) parts.push(`Agregadas: ${stats.added}`);
    if (stats.removed > 0) parts.push(`Eliminadas: ${stats.removed}`);
    if (stats.instrument_changes > 0) parts.push(`Instrumentos: ${stats.instrument_changes}`);
    if (stats.velocity_changes > 0) parts.push(`Velocidades: ${stats.velocity_changes}`);
    if (stats.timing_adjustments > 0) parts.push(`Timing: ${stats.timing_adjustments}`);
    if (stats.key_adjustments > 0) parts.push(`Tonos: ${stats.key_adjustments}`);
    if (stats.repeat_duplicates > 0) parts.push(`Repetidas: ${stats.repeat_duplicates}`);
    
    const changesText = parts.length > 0 ? ` (${parts.join(', ')})` : '';
    const msg = `✓ Optimizado: ${stats.original_count || noteData.length} -> ${stats.optimized_count || noteData.length} notas${changesText}`;
    
    setStatus(msg);
    $('btn-optimize').disabled = false;
  } catch(err) {
    setStatus('Error: ' + err.message);
    $('btn-optimize').disabled = false;
  }
}

function onNoteSelect(note) {
    if (!note) {
        $('btn-delete-note').disabled = true;
        $('btn-save-note').disabled = true;
        return;
    }
    $('btn-delete-note').disabled = false;
    $('btn-save-note').disabled = false;
    $('prop-tick').value = note.tick;
    $('prop-key').value = note.key;
    $('prop-inst').value = note.instrument || 0;
    $('prop-vel').value = note.velocity || 100;
    $('prop-pan').value = note.panning || 100;
    $('val-vel').textContent = note.velocity || 100;
    $('val-pan').textContent = note.panning || 100;
}

function onNotesChanged(newNotes) {
    noteData = newNotes;
    updateNoteCount();
    updateTable();
}

async function onSaveNote() {
    const note = pianoRoll.selectedNote;
    if (!note) return;
    note.tick = parseInt($('prop-tick').value);
    note.key = parseInt($('prop-key').value);
    note.instrument = parseInt($('prop-inst').value);
    note.velocity = parseInt($('prop-vel').value);
    note.panning = parseInt($('prop-pan').value);
    pianoRoll.draw();
    await API.saveNotes(sessionId, noteData);
    setStatus('✓ Nota guardada');
}

async function onAddNote() {
    const newNote = { tick: 0, key: 45, instrument: 0, velocity: 100, panning: 100, layer: 0 };
    noteData.push(newNote);
    noteData.sort((a, b) => a.tick - b.tick);
    pianoRoll.setNotes(noteData);
    pianoRoll.draw();
    updateNoteCount();
    updateTable();
    await API.saveNotes(sessionId, noteData);
}

async function onDeleteNote() {
    const note = pianoRoll.selectedNote;
    if (!note) return;
    const idx = noteData.indexOf(note);
    if (idx >= 0) {
        noteData.splice(idx, 1);
        pianoRoll.setNotes(noteData);
        pianoRoll.draw();
        updateNoteCount();
        updateTable();
        await API.saveNotes(sessionId, noteData);
    }
}

async function onSyncTable() {
    updateTable();
    pianoRoll.setNotes(noteData);
    pianoRoll.draw();
    await API.saveNotes(sessionId, noteData);
    setStatus('✓ Tabla sincronizada');
}

async function onDownload() {
    try {
        const blob = await API.downloadNbs(sessionId);
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'song.nbs';
        a.click();
        setStatus('✓ NBS descargado');
    } catch(err) {
        setStatus('Error: ' + err.message);
    }
}

function updateNoteCount() {
    $('note-count').textContent = `${noteData.length} notas`;
}

function updateStats(notes) {
    if (!notes) return;
    const instCount = {};
    notes.forEach(n => { instCount[n.instrument || 0] = (instCount[n.instrument || 0] || 0) + 1; });
    $('stats').innerHTML = Object.entries(instCount)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([i, c]) => `${INST_NAMES[i] || 'Inst'+i}: ${c}`)
        .join('<br>');
}

function updateTable() {
    const tbody = $('table-body');
    tbody.innerHTML = '';
    noteData.slice(0, 100).forEach((n, i) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${n.tick}</td><td>${n.key}</td><td>${n.instrument || 0}</td><td>${n.velocity || 100}</td><td>${n.panning || 100}</td>`;
        tr.onclick = () => {
            pianoRoll.selectNote(n);
            pianoRoll.draw();
            onNoteSelect(n);
        };
        tbody.appendChild(tr);
    });
}

function setStatus(msg) {
    $('status').textContent = msg;
}

// Training functions
let uploadedFiles = [];

async function onUploadPair() {
  const nbsFile = $('train-nbs').files[0];
  const audioFile = $('train-audio').files[0];
  if (!nbsFile || !audioFile) {
    setStatus('Subí NBS + audio');
    return;
  }

  try {
    setStatus('Subiendo par...');
    await API.uploadPair(nbsFile, audioFile);
    
    // Add to uploaded files list
    uploadedFiles.push({
      nbs: nbsFile.name,
      audio: audioFile.name
    });
    updateTrainingList();
    
    setStatus(`✓ Par subido: ${nbsFile.name}`);
    $('train-nbs').value = '';
    $('train-audio').value = '';
  } catch(err) {
    setStatus('Error: ' + err.message);
  }
}

function updateTrainingList() {
  const list = $('training-files-list');
  if (!list) return;
  
  if (uploadedFiles.length === 0) {
    list.innerHTML = '<li>Ningún archivo subido aún</li>';
  } else {
    list.innerHTML = uploadedFiles.map(f => 
      `<li>📁 ${f.nbs} + 🎵 ${f.audio}</li>`
    ).join('');
  }
  
  const status = $('train-status');
  if (status && uploadedFiles.length > 0) {
    status.textContent = `${uploadedFiles.length} par(es) subido(s). Click en "🔄 Reentrenar" para entrenar.`;
        setStatus('Error: ' + err.message);
    }
}

async function onRelearn() {
  try {
    $('btn-relearn').disabled = true;
    setStatus('Cargando perfil actual...');
    
    // Primero cargar el perfil actual
    const currentProfile = await API.getProfile();
    console.log('Profile actual:', currentProfile);
    
    $('train-status').textContent = `📊 Actual: ${currentProfile.songs_analyzed || 0} canciones, ${(currentProfile.total_notes || 0).toLocaleString()} notas`;
    
    setStatus('Reentrenando modelo de audio...');
    const result = await API.relearn();
    
    const notes = result.notes_extracted || 0;
    const instruments = result.instruments_trained || 0;
    
    $('train-status').textContent = `✓ Modelo: ${notes.toLocaleString()} notas, ${instruments} instrumentos`;
    setStatus(`✓ Modelo reentrenado: ${notes.toLocaleString()} notas en ${instruments} instrumentos`);
    $('btn-relearn').disabled = false;
  } catch(err) {
    console.error('Error en relearn:', err);
    $('train-status').textContent = `✗ Error: ${err.message}`;
    setStatus('Error: ' + err.message);
    $('btn-relearn').disabled = false;
  }
}

async function onGenProfile() {
  try {
    $('btn-gen-profile').disabled = true;
    setStatus('Generando perfil base...');
    $('train-status').textContent = '⏳ Generando perfil...';
    
    const result = await API.genBaseProfile();
    
    $('train-status').textContent = `✓ Perfil: ${result.songs_analyzed || 0} canciones analizadas`;
    setStatus('✓ Perfil generado correctamente');
    $('btn-gen-profile').disabled = false;
  } catch(err) {
    $('train-status').textContent = `✗ Error: ${err.message}`;
    setStatus('Error: ' + err.message);
    $('btn-gen-profile').disabled = false;
  }
}

// Iniciar
window.addEventListener('DOMContentLoaded', async () => {
  console.log('DOMContentLoaded fired');
  try {
    await init();
    console.log('init() completed successfully');
    
    // Mostrar estado del modelo
    try {
      const profile = await API.getProfile();
      const trainStatus = $('train-status');
      if (trainStatus && profile) {
        trainStatus.textContent = `📊 Modelo: ${profile.songs_analyzed || 0} canciones, ${(profile.total_notes || 0).toLocaleString()} notas`;
        console.log(`Modelo cargado: ${profile.songs_analyzed} canciones, ${profile.total_notes} notas`);
      }
    } catch(e) {
      console.log('No hay perfil cargado aún');
    }
  } catch(err) {
    console.error('Error in init():', err);
    console.error('Stack:', err.stack);
    const status = document.getElementById('status');
    if (status) {
      status.textContent = 'Error: ' + err.message;
    }
  }
});
