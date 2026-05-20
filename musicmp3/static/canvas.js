// Interactive piano roll canvas with scrolling
class PianoRoll {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.notes = [];
    this.selectedIdx = -1;
    this.zoom = 1;
    this.viewStart = 0;
    this.keyRange = [0, 87];
    this.tickRange = [0, 100];
    this.dragging = false;
    this.dragNoteIdx = -1;
    this.panning = false;
    this.panStartX = 0;
    this.panStartView = 0;
    this.dragOffX = 0;
    this.dragOffY = 0;
    this.onSelect = null;
    this.onChange = null;
    this.playbackTick = -1;
    this.tempo_bps = 10;

    this.colors = {
      0:'#e74c3c',1:'#3498db',2:'#2ecc71',3:'#f1c40f',
      4:'#9b59b6',5:'#1abc9c',6:'#e67e22',7:'#34495e',
      8:'#16a085',9:'#c0392b',10:'#2980b9',11:'#27ae60',
      12:'#f39c12',13:'#8e44ad',14:'#d35400',15:'#7f8c8d',
    };
    this.noteNames = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];

    this._initEvents();
    this._resize();
    window.addEventListener('resize', () => this._resize());
  }

  _resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width * devicePixelRatio;
    this.canvas.height = rect.height * devicePixelRatio;
    this.canvas.style.width = rect.width + 'px';
    this.canvas.style.height = rect.height + 'px';
    this.w = rect.width;
    this.h = rect.height;
    this.dpr = devicePixelRatio;
    this.draw();
  }

  _noteName(k) {
    const m = k + 21;
    return `${this.noteNames[m % 12]}${Math.floor(m / 12) - 1}`;
  }

  _tickX(tick) { return 60 + (tick - this.viewStart) * this.zoom * 8; }
  _keyY(key) { return this.h - 25 - (key - this.keyRange[0]) * (this.h - 45) / (this.keyRange[1] - this.keyRange[0] + 1); }
  _xTick(x) { return Math.round((x - 60) / (this.zoom * 8) + this.viewStart); }
  _yKey(y) { return Math.round(this.keyRange[1] - (y - 25) * (this.keyRange[1] - this.keyRange[0] + 1) / (this.h - 45)); }
  _visibleTicks() { return Math.max(1, (this.w - 60) / (this.zoom * 8)); }

  _constrainView() {
    const total = this.tickRange[1] - this.tickRange[0];
    const vis = this._visibleTicks();
    this.viewStart = Math.max(this.tickRange[0], Math.min(this.viewStart, this.tickRange[1] - vis));
  }

  setNotes(notes) {
    this.notes = notes;
    if (notes.length) {
      this.tickRange = [Math.max(0, Math.min(...notes.map(n => n.tick)) - 4), Math.max(...notes.map(n => n.tick)) + 8];
      this.viewStart = this.tickRange[0];
    }
    this.selectedIdx = -1;
    this.playbackTick = -1;
    this.draw();
  }

  setTempo(bps) { this.tempo_bps = bps; }

  setPlaybackTick(tick) {
    this.playbackTick = tick;
    this.draw();
  }

  draw() {
    const {ctx, w, h, dpr} = this;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const keyCount = this.keyRange[1] - this.keyRange[0] + 1;
    const keyH = (h - 45) / keyCount;
    const viewEnd = this.viewStart + this._visibleTicks();
    const total = this.tickRange[1] - this.tickRange[0];

    ctx.fillStyle = '#0d1b2a';
    ctx.fillRect(0, 0, w, h);

    // Grid lines
    ctx.strokeStyle = '#1a2a4a';
    ctx.lineWidth = 0.5;
    for (let k = this.keyRange[0]; k <= this.keyRange[1]; k++) {
      const y = this._keyY(k);
      const midi = k + 21;
      const isC = midi % 12 === 0;
      ctx.fillStyle = isC ? '#2a3a5a' : '#1a2a4a';
      ctx.fillRect(0, y - keyH/2, w, keyH);
      ctx.strokeStyle = '#2a3a5a';
      ctx.beginPath();
      ctx.moveTo(40, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Beat lines (only visible ones)
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    const beatStep = Math.max(1, Math.floor(40 / this.zoom));
    const firstBeat = Math.ceil(this.viewStart / beatStep) * beatStep;
    for (let t = firstBeat; t <= viewEnd; t += beatStep) {
      if (t % 10 === 0) {
        const x = this._tickX(t);
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h - 25);
        ctx.stroke();
      }
    }

    // Tick markers (visible)
    ctx.fillStyle = '#555';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    const tickStep = Math.max(1, Math.floor(40 / this.zoom));
    const firstTick = Math.ceil(this.viewStart / tickStep) * tickStep;
    for (let t = firstTick; t <= viewEnd; t += tickStep) {
      const x = this._tickX(t);
      ctx.fillText(t, x, h - 10);
    }

    // Key labels
    ctx.textAlign = 'right';
    ctx.font = '10px sans-serif';
    for (let k = this.keyRange[0]; k <= this.keyRange[1]; k++) {
      const y = this._keyY(k);
      const name = this._noteName(k);
      ctx.fillStyle = '#666';
      ctx.fillText(`${k} ${name}`, 36, y + 4);
    }

    // Notes (only visible)
    for (let i = 0; i < this.notes.length; i++) {
      const n = this.notes[i];
      if (n.tick < this.viewStart - 2 || n.tick > viewEnd + 2) continue;
      const x = this._tickX(n.tick);
      const y = this._keyY(n.key);
      const nw = Math.max(4, this.zoom * 8 - 1);
      const nh = keyH - 1;
      const color = this.colors[n.instrument] || '#888';
      ctx.fillStyle = i === this.selectedIdx ? '#fff' : color;
      ctx.fillRect(x, y - nh/2, nw, nh);
      ctx.strokeStyle = i === this.selectedIdx ? '#e94560' : 'rgba(0,0,0,0.3)';
      ctx.lineWidth = i === this.selectedIdx ? 2 : 0.5;
      ctx.strokeRect(x, y - nh/2, nw, nh);
    }

    // Playback line
    if (this.playbackTick >= 0) {
      const px = this._tickX(this.playbackTick);
      const grad = ctx.createRadialGradient(px, h / 2, 0, px, h / 2, 30);
      grad.addColorStop(0, 'rgba(0, 255, 200, 0.3)');
      grad.addColorStop(1, 'rgba(0, 255, 200, 0)');
      ctx.fillStyle = grad;
      ctx.fillRect(px - 30, 0, 60, h - 25);
      ctx.strokeStyle = '#00ffc8';
      ctx.lineWidth = 2;
      ctx.shadowColor = '#00ffc8';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(px, 0);
      ctx.lineTo(px, h - 25);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // Scrollbar at bottom
    const sbY = h - 4;
    const sbH = 4;
    const sbW = w - 60;
    ctx.fillStyle = '#1a2a4a';
    ctx.fillRect(60, sbY, sbW, sbH);
    if (total > 0) {
      const vis = this._visibleTicks();
      const barW = Math.max(20, sbW * (vis / total));
      const barX = 60 + sbW * ((this.viewStart - this.tickRange[0]) / total);
      ctx.fillStyle = '#e94560';
      ctx.fillRect(barX, sbY, barW, sbH);
    }
  }

  _initEvents() {
    this.canvas.addEventListener('mousedown', e => this._onMouseDown(e));
    this.canvas.addEventListener('mousemove', e => this._onMouseMove(e));
    this.canvas.addEventListener('mouseup', e => this._onMouseUp(e));
    this.canvas.addEventListener('mouseleave', e => this._onMouseUp(e));
    this.canvas.addEventListener('wheel', e => {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        const oldZoom = this.zoom;
        this.zoom = Math.max(0.2, Math.min(10, this.zoom - e.deltaY * 0.01));
        const midTick = this.viewStart + this._visibleTicks() / 2;
        this.viewStart = midTick - this._visibleTicks() / 2;
        document.getElementById('zoom-info').textContent = `Zoom: ${this.zoom.toFixed(1)}x`;
      } else {
        const step = Math.max(5, Math.floor(this._visibleTicks() * 0.15));
        this.viewStart += e.deltaY > 0 ? step : -step;
      }
      this._constrainView();
      this.draw();
    }, { passive: false });
  }

  _getNoteAt(x, y) {
    const keyCount = this.keyRange[1] - this.keyRange[0] + 1;
    const keyH = (this.h - 45) / keyCount;
    const viewEnd = this.viewStart + this._visibleTicks();
    for (let i = this.notes.length - 1; i >= 0; i--) {
      const n = this.notes[i];
      if (n.tick < this.viewStart - 2 || n.tick > viewEnd + 2) continue;
      const nx = this._tickX(n.tick);
      const ny = this._keyY(n.key);
      const nw = Math.max(4, this.zoom * 8 - 1);
      const nh = keyH - 1;
      if (x >= nx && x <= nx + nw && y >= ny - nh/2 && y <= ny + nh/2) return i;
    }
    return -1;
  }

  _onMouseDown(e) {
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const idx = this._getNoteAt(x, y);
    if (idx >= 0) {
      this.selectedIdx = idx;
      this.dragging = true;
      this.dragNoteIdx = idx;
      const n = this.notes[idx];
      this.dragOffX = x - this._tickX(n.tick);
      this.dragOffY = y - this._keyY(n.key);
      if (this.onSelect) this.onSelect(idx);
    } else {
      this.selectedIdx = -1;
      this.panning = true;
      this.panStartX = x;
      this.panStartView = this.viewStart;
      if (this.onSelect) this.onSelect(-1);
    }
    this.draw();
  }

  _onMouseMove(e) {
    if (this.dragging && this.dragNoteIdx >= 0) {
      const rect = this.canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const n = this.notes[this.dragNoteIdx];
      const newTick = Math.max(0, this._xTick(x - this.dragOffX));
      const newKey = Math.max(0, Math.min(87, this._yKey(y - this.dragOffY)));
      n.tick = newTick;
      n.key = newKey;
      if (this.onChange) this.onChange();
      this.draw();
    } else if (this.panning) {
      const rect = this.canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const dx = (x - this.panStartX) / (this.zoom * 8);
      this.viewStart = this.panStartView - dx;
      this._constrainView();
      this.draw();
    }
  }

  _onMouseUp(e) {
    if (this.dragging && this.dragNoteIdx >= 0) {
      if (this.onChange) this.onChange(true);
    }
    this.dragging = false;
    this.dragNoteIdx = -1;
    this.panning = false;
  }
}
