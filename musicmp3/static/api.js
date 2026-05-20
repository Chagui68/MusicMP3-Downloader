// API client
const API = {
    async createSession() {
        const r = await fetch('/api/session', { method: 'POST' });
        return r.json();
    },
    
    async uploadNbs(file, sessionId) {
        const fd = new FormData();
        fd.append('session_id', sessionId);
        fd.append('file', file, file.name);
        const r = await fetch('/api/upload-nbs', { method: 'POST', body: fd });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Upload failed'); }
        return r.json();
    },
    
    async convert(sessionId, data) {
        const fd = new FormData();
        fd.append('session_id', sessionId);
        fd.append('target_low', data.target_low);
        fd.append('target_high', data.target_high);
        fd.append('transpose', data.transpose);
        fd.append('mode', data.mode || 'full');
        if (data.query) fd.append('query', data.query);
        if (data.file) fd.append('file', data.file, data.file.name);
        const r = await fetch('/api/convert', { method: 'POST', body: fd });
        if (!r.ok) { const e = await r.text(); throw new Error(e); }
        return r.json();
    },
    
    async getNotes(sessionId) {
        const r = await fetch(`/api/session/${sessionId}/notes`);
        if (!r.ok) throw new Error('No session');
        return r.json();
    },
    
    async saveNotes(sessionId, notes) {
        const r = await fetch(`/api/session/${sessionId}/notes`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notes }),
        });
        if (!r.ok) throw new Error('Save failed');
        return r.json();
    },
    
    async render(sessionId) {
        const r = await fetch(`/api/session/${sessionId}/render`, { method: 'POST' });
        if (!r.ok) throw new Error('Render failed');
        return r.json();
    },
    
    async optimize(sessionId) {
        const r = await fetch(`/api/session/${sessionId}/optimize`, { method: 'POST' });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Optimize failed'); }
        return r.json();
    },
    
    async downloadNbs(sessionId) {
        const r = await fetch(`/api/session/${sessionId}/nbs`);
        if (!r.ok) throw new Error('Download failed');
        return r.blob();
    },
    
    async downloadWav(sessionId) {
        const r = await fetch(`/api/session/${sessionId}/audio`);
        if (!r.ok) throw new Error('WAV download failed');
        return r.blob();
    },
    
    async genBaseProfile() {
        const r = await fetch('/api/profile/gen-base', { method: 'POST' });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Failed'); }
        return r.json();
    },
    
    async generateProfile(nbsDir) {
        const fd = new FormData();
        fd.append('nbs_dir', nbsDir);
        const r = await fetch('/api/profile/generate', { method: 'POST', body: fd });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Profile gen failed'); }
        return r.json();
    },
    
    async getProfile() {
        const r = await fetch('/api/profile');
        if (!r.ok) return null;
        return r.json();
    },
    
    async getAudioModel() {
        const r = await fetch('/api/profile/model');
        if (!r.ok) return null;
        return r.json();
    },
    
    async uploadPair(nbsFile, audioFile) {
        const fd = new FormData();
        fd.append('nbs', nbsFile, nbsFile.name);
        fd.append('audio', audioFile, audioFile.name);
        const r = await fetch('/api/profile/upload-pair', { method: 'POST', body: fd });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Upload failed'); }
        return r.json();
    },
    
    async relearn() {
        const r = await fetch('/api/profile/relearn', { method: 'POST' });
        if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Relearn failed'); }
        return r.json();
    },
};
