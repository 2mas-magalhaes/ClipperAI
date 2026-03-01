/* ═══════════════════════════════════════════════
   ClipAI — Frontend Application
   ═══════════════════════════════════════════════ */

// ── State ──
let currentPage = 'dashboard';
let queueData = [];
let channelsData = [];
let followedChannelsData = [];
let followedVideosData = [];
let selectedFollowedId = null;
let reviewData = [];
let postedData = [];
let settingsData = {};
let workerRunning = false;
let workerPaused = false;

// ── Polling interval ──
let pollInterval = null;

// ═══════════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            navigateTo(item.dataset.page);
        });
    });

    // Initial load
    refreshAll();

    // Start polling every 3 seconds
    pollInterval = setInterval(pollUpdates, 3000);
});

function navigateTo(page) {
    currentPage = page;

    // Update nav
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.querySelector(`.nav-item[data-page="${page}"]`).classList.add('active');

    // Show page
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${page}`).classList.add('active');

    // Refresh page data
    refreshPage(page);
}

function refreshAll() {
    fetchQueue();
    fetchChannels();
    fetchFollowedChannels();
    fetchReview();
    fetchPosted();
    fetchSettings();
    fetchWorkerStatus();
}

function refreshPage(page) {
    switch (page) {
        case 'dashboard':
            fetchQueue();
            fetchPosted();
            break;
        case 'queue':
            fetchQueue();
            break;
        case 'channels':
            fetchChannels();
            break;
        case 'followed':
            fetchFollowedChannels();
            if (selectedFollowedId) {
                fetchFollowedVideos(selectedFollowedId);
            }
            break;
        case 'review':
            fetchReview();
            break;
        case 'posted':
            fetchPosted();
            break;
        case 'settings':
            fetchSettings();
            checkOllama();
            break;
    }
}

function pollUpdates() {
    fetchQueue();
    if (currentPage === 'followed') {
        fetchFollowedChannels();
        if (selectedFollowedId) fetchFollowedVideos(selectedFollowedId);
    }
    // Só atualizar badge da revisão — não refazer o DOM (vídeos reiniciam)
    if (currentPage !== 'review') {
        fetchReviewBadgeOnly();
    }
    fetchWorkerStatus();
    if (currentPage === 'dashboard') {
        fetchCurrentProcessing();
    }
}

async function fetchReviewBadgeOnly() {
    reviewData = await api('/api/review');
    updateReviewBadge();
}

// ═══════════════════════════════════════════════
//  API HELPERS
// ═══════════════════════════════════════════════

async function api(url, method = 'GET', body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    return res.json();
}

// ═══════════════════════════════════════════════
//  QUEUE
// ═══════════════════════════════════════════════

async function fetchQueue() {
    queueData = await api('/api/queue');
    renderQueue();
    updateDashboardStats();
}

function renderQueue() {
    const tbody = document.getElementById('queue-tbody');
    const empty = document.getElementById('queue-empty');

    if (!queueData || queueData.length === 0) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        document.getElementById('queue-badge').textContent = '0';
        return;
    }

    empty.style.display = 'none';
    const queuedCount = queueData.filter(q => q.status === 'queued').length;
    document.getElementById('queue-badge').textContent = queuedCount || '';

    tbody.innerHTML = queueData.map((item, idx) => {
        const channelName = getChannelName(item.channel_id);
        const statusBadge = renderStatusBadge(item.status);
        const progress = renderProgress(item);
        const clipsText = item.status === 'done'
            ? `<span style="color:var(--green)">${item.clips_done}/${item.clips_total}</span>`
            : item.clips_total > 0
                ? `${item.clips_done}/${item.clips_total}`
                : '—';

        return `<tr draggable="true" data-queue-id="${item.id}" data-index="${idx}">
            <td class="drag-handle" style="cursor:grab;color:var(--text-muted);text-align:center">
                <i class="fas fa-grip-vertical"></i>
            </td>
            <td style="color:var(--text-muted)">${idx + 1}</td>
            <td>
                <div style="font-weight:500">${esc(item.title)}</div>
                <div style="font-size:0.75rem;color:var(--text-muted);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                    ${item.source_channel_name ? `<span class="tag" style="font-size:0.7rem;padding:2px 8px;margin-right:4px">${esc(item.source_channel_name)}</span>` : ''}
                    ${esc(item.url)}
                </div>
            </td>
            <td>${channelName ? `<span class="tag">${esc(channelName)}</span>` : '<span style="color:var(--text-muted)">—</span>'}</td>
            <td>${statusBadge}</td>
            <td style="min-width:120px">${progress}</td>
            <td>${clipsText}</td>
            <td>
                <label class="auto-pub-toggle" title="Publicar automaticamente">
                    <input type="checkbox" ${item.auto_publish ? 'checked' : ''}
                        ${item.status !== 'queued' ? 'disabled' : ''}
                        onchange="setQueueAutoPublish('${item.id}', this.checked)">
                    <span class="auto-pub-label">Auto</span>
                </label>
            </td>
            <td>
                <div style="display:flex;gap:4px">
                    ${item.status === 'queued' ? `<button class="btn btn-icon btn-sm" title="Remover" onclick="removeFromQueue('${item.id}')"><i class="fas fa-trash" style="color:var(--red)"></i></button>` : ''}
                    ${item.status === 'error' ? `<button class="btn btn-icon btn-sm" title="Tentar de novo" onclick="retryQueueItem('${item.id}')"><i class="fas fa-redo" style="color:var(--orange)"></i></button>` : ''}
                    ${item.status === 'done' ? `<button class="btn btn-icon btn-sm" title="Ver clips" onclick="showClips('${item.id}')"><i class="fas fa-film" style="color:var(--green)"></i></button>` : ''}
                </div>
            </td>
        </tr>`;
    }).join('');
    
    // Setup drag-and-drop handlers
    setupQueueDragAndDrop();
}

// === DRAG AND DROP ===
let draggedElement = null;
let dragOverElement = null;

function setupQueueDragAndDrop() {
    const tbody = document.getElementById('queue-tbody');
    if (!tbody) return;

    // Use event delegation on tbody for robustness
    tbody.addEventListener('dragstart', e => {
        const row = e.target.closest('tr[draggable="true"]');
        if (!row) return;
        draggedElement = row;
        draggedElement.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', row.dataset.queueId);
    });

    tbody.addEventListener('dragover', e => {
        e.preventDefault();
        const row = e.target.closest('tr[draggable="true"]');
        if (!row || row === draggedElement) return;
        if (row === dragOverElement) return;

        // Remove previous highlight
        if (dragOverElement) dragOverElement.classList.remove('drag-over');
        dragOverElement = row;
        dragOverElement.classList.add('drag-over');

        // Visual insert position
        const rect = row.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        if (e.clientY < midY) {
            tbody.insertBefore(draggedElement, row);
        } else {
            tbody.insertBefore(draggedElement, row.nextSibling);
        }
    });

    tbody.addEventListener('dragleave', e => {
        if (!tbody.contains(e.relatedTarget)) {
            if (dragOverElement) dragOverElement.classList.remove('drag-over');
            dragOverElement = null;
        }
    });

    tbody.addEventListener('drop', e => {
        e.preventDefault();
        e.stopPropagation();
        if (dragOverElement) dragOverElement.classList.remove('drag-over');
        dragOverElement = null;

        const newOrder = Array.from(tbody.querySelectorAll('tr[data-queue-id]'))
            .map(row => row.dataset.queueId);
        reorderQueue(newOrder);
    });

    tbody.addEventListener('dragend', e => {
        if (draggedElement) draggedElement.classList.remove('dragging');
        if (dragOverElement) dragOverElement.classList.remove('drag-over');
        draggedElement = null;
        dragOverElement = null;
    });
}

async function reorderQueue(newOrder) {
    try {
        const response = await fetch('/api/queue/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order: newOrder })
        });
        
        if (!response.ok) {
            throw new Error('Erro ao reordenar');
        }
        
        await loadQueue();
    } catch (error) {
        console.error('Erro ao reordenar queue:', error);
        showNotification('Erro ao reordenar queue', 'error');
        await loadQueue(); // Reload to reset visual state
    }
}

function renderStatusBadge(status) {
    const map = {
        queued: { icon: 'fas fa-clock', label: 'Na Queue' },
        downloading: { icon: 'fas fa-spinner', label: 'Download' },
        analyzing: { icon: 'fas fa-spinner', label: 'Análise' },
        editing: { icon: 'fas fa-spinner', label: 'Edição' },
        done: { icon: 'fas fa-check', label: 'Concluído' },
        error: { icon: 'fas fa-exclamation-triangle', label: 'Erro' },
        cancelled: { icon: 'fas fa-ban', label: 'Cancelado' },
    };
    const s = map[status] || { icon: 'fas fa-question', label: status };
    return `<span class="status-badge ${status}"><i class="${s.icon}"></i> ${s.label}</span>`;
}

function renderProgress(item) {
    if (item.status === 'queued') return '<span style="color:var(--text-muted);font-size:0.8rem">A aguardar</span>';
    if (item.status === 'done') {
        return `<div class="progress-bar"><div class="fill done" style="width:100%"></div></div>
                <div class="progress-text">Concluído</div>`;
    }
    if (item.status === 'error') {
        return `<div class="progress-bar"><div class="fill error" style="width:100%"></div></div>
                <div class="progress-text" style="color:var(--red)" title="${esc(item.error_msg)}">${esc(item.error_msg || 'Erro').substring(0, 40)}</div>`;
    }
    return `<div class="progress-bar"><div class="fill" style="width:${item.progress}%"></div></div>
            <div class="progress-text">${item.progress}% — ${esc(item.status_detail || '')}</div>`;
}

async function setQueueAutoPublish(id, value) {
    await api(`/api/queue/${id}`, 'PATCH', { auto_publish: value });
    const item = queueData.find(q => q.id === id);
    if (item) item.auto_publish = value;
}

async function removeFromQueue(id) {
    await api(`/api/queue/${id}`, 'DELETE');
    toast('Vídeo removido da queue', 'info');
    fetchQueue();
}

async function retryQueueItem(id) {
    await api(`/api/queue/${id}`, 'PATCH', { status: 'queued', progress: 0, error_msg: '', status_detail: '' });
    toast('Vídeo re-adicionado à queue', 'info');
    fetchQueue();
}

function showClips(id) {
    const item = queueData.find(q => q.id === id);
    if (!item || !item.clips || item.clips.length === 0) {
        toast('Sem clips disponíveis', 'error');
        return;
    }
    navigateTo('review');
}

// ═══════════════════════════════════════════════
//  REVIEW CLIPS
// ═══════════════════════════════════════════════

async function fetchReview() {
    reviewData = await api('/api/review');
    renderReview();
    updateReviewBadge();
}

function renderReview() {
    const grid = document.getElementById('review-grid');
    const empty = document.getElementById('review-empty');
    if (!grid || !empty) return;

    const pending = (reviewData || []).filter(c => c.status === 'pending');
    if (pending.length === 0) {
        grid.innerHTML = '';
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';
    grid.innerHTML = pending.map(clip => {
        const channelName = getChannelName(clip.channel_id);
        const clipUrl = clipPathToUrl(clip.clip_path);
        const youtubeTitle = clip.youtube?.titulo || clip.title || 'Clip';

        // Source video info
        const srcUrl   = clip.source_url  || '';
        const srcTitle = clip.source_title || 'Vídeo original';
        const srcChan  = clip.source_channel_name || '';
        // YouTube video ID → thumbnail
        let srcThumb = '';
        const vidMatch = srcUrl.match(/[?&]v=([A-Za-z0-9_-]{11})/);
        if (vidMatch) srcThumb = `https://img.youtube.com/vi/${vidMatch[1]}/mqdefault.jpg`;

        const sourceBlock = srcUrl
            ? `<div class="review-source">
                <div class="review-source-label"><i class="fas fa-film"></i> Origem do clipe</div>
                <a class="review-source-link" href="${esc(srcUrl)}" target="_blank" rel="noopener">
                    ${srcThumb ? `<img class="review-source-thumb" src="${esc(srcThumb)}" alt="">` : ''}
                    <div class="review-source-info">
                        <div class="review-source-title">${esc(srcTitle)}</div>
                        ${srcChan ? `<div class="review-source-chan"><i class="fab fa-youtube"></i> ${esc(srcChan)}</div>` : ''}
                    </div>
                </a>
               </div>`
            : '';

        return `
        <div class="review-card">
            <video class="review-video" controls preload="metadata" src="${esc(clipUrl)}"></video>
            <div class="review-content">
                <div class="review-title">${esc(youtubeTitle)}</div>
                <div class="review-meta">
                    ${channelName ? `<span class="tag">${esc(channelName)}</span>` : '<span class="tag muted">Sem canal</span>'}
                    ${clip.reason ? `<span class="text-muted">${esc(clip.reason)}</span>` : ''}
                </div>
                ${sourceBlock}
                <div class="form-group" style="margin-top:10px">
                    <label>Canal para publicar</label>
                    <select class="form-control" onchange="setReviewChannel('${clip.id}', this.value)">
                        <option value="">— Selecionar canal —</option>
                        ${channelsData.map(ch => `<option value="${ch.id}" ${clip.channel_id === ch.id ? 'selected' : ''}>${esc(ch.name)}</option>`).join('')}
                    </select>
                </div>
                <div class="review-actions">
                    <button class="btn btn-success" onclick="publishReviewClip('${clip.id}')">
                        <i class="fas fa-upload"></i> Publicar
                    </button>
                    <button class="btn btn-danger" onclick="rejectReviewClip('${clip.id}')">
                        <i class="fas fa-times"></i> Rejeitar
                    </button>
                </div>
            </div>
        </div>`;
    }).join('');
}

function updateReviewBadge() {
    const pending = (reviewData || []).filter(c => c.status === 'pending').length;
    const badge = document.getElementById('review-badge');
    if (badge) badge.textContent = pending || '';
}

function clipPathToUrl(path) {
    if (!path) return '';
    const normalized = String(path).replaceAll('\\', '/');
    const filename = normalized.split('/').pop();
    return `/clips/${filename}`;
}

async function setReviewChannel(clipId, channelId) {
    await api(`/api/review/${clipId}`, 'PATCH', { channel_id: channelId || null });
    const found = reviewData.find(c => c.id === clipId);
    if (found) found.channel_id = channelId || null;
}

async function publishReviewClip(clipId) {
    const clip = reviewData.find(c => c.id === clipId);
    if (!clip) return;
    const result = await api(`/api/review/${clipId}/publish`, 'POST', { channel_id: clip.channel_id || null });
    if (result.error) {
        toast(result.error, 'error');
        return;
    }
    toast('Clip publicado!', 'success');
    await fetchReview();
    await fetchPosted();
    await fetchChannels();
}

async function rejectReviewClip(clipId) {
    await api(`/api/review/${clipId}`, 'DELETE');
    toast('Clip rejeitado', 'info');
    await fetchReview();
}

// ═══════════════════════════════════════════════
//  ADD VIDEO MODAL
// ═══════════════════════════════════════════════

function openAddVideoModal() {
    populateChannelSelect('video-channel');
    document.getElementById('video-url').value = '';
    document.getElementById('video-title').value = '';
    // Pre-preenche o checkbox com o valor global
    document.getElementById('video-auto-publish').checked = settingsData.auto_publish || false;
    document.getElementById('modal-add-video').style.display = 'flex';
    document.getElementById('video-url').focus();
}

async function addVideoToQueue() {
    const url = document.getElementById('video-url').value.trim();
    const title = document.getElementById('video-title').value.trim();
    const channelId = document.getElementById('video-channel').value;
    const autoPublish = document.getElementById('video-auto-publish').checked;

    if (!url) {
        toast('URL é obrigatória', 'error');
        return;
    }

    await api('/api/queue', 'POST', { url, title, channel_id: channelId || null, auto_publish: autoPublish });
    closeModal('modal-add-video');
    toast('Vídeo adicionado à queue!', 'success');
    fetchQueue();
}

// ═══════════════════════════════════════════════
//  CHANNELS
// ═══════════════════════════════════════════════

async function fetchChannels() {
    channelsData = await api('/api/channels');
    renderChannels();
    populateChannelSelects();
}

function renderChannels() {
    const grid = document.getElementById('channels-grid');
    const empty = document.getElementById('channels-empty');

    if (!channelsData || channelsData.length === 0) {
        grid.innerHTML = '';
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';
    grid.innerHTML = channelsData.map(ch => `
        <div class="channel-card">
            ${ch.active ? '<span class="channel-badge">Ativo</span>' : ''}
            <div class="channel-header">
                ${ch.channel_thumbnail ? `<img class="channel-avatar-img" src="${esc(ch.channel_thumbnail)}" alt="${esc(ch.name)}" onerror="this.style.display='none'">` : ''}
                <div class="channel-avatar" ${ch.channel_thumbnail ? 'style="display:none"' : ''}><i class="fab fa-youtube"></i></div>
                <div>
                    <div class="channel-name">${esc(ch.name)}</div>
                    <div class="channel-url">${esc(ch.channel_url || 'Sem URL')}</div>
                </div>
            </div>
            <div class="channel-stats">
                <div class="channel-stat">
                    <div class="val">${ch.videos_posted || 0}</div>
                    <div class="lbl">Vídeos</div>
                </div>
                <div class="channel-stat">
                    <div class="val">${formatNumber(ch.total_views || 0)}</div>
                    <div class="lbl">Views</div>
                </div>
                <div class="channel-stat">
                    <div class="val">${formatNumber(ch.total_likes || 0)}</div>
                    <div class="lbl">Likes</div>
                </div>
            </div>
            ${ch.description ? `<div style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:12px">${esc(ch.description)}</div>` : ''}
            <div class="channel-actions">
                <button class="btn btn-sm" onclick="testChannelPublish('${ch.id}', '${esc(ch.name)}')">
                    <i class="fas fa-flask"></i> Testar
                </button>
                <button class="btn btn-sm" onclick="toggleChannel('${ch.id}', ${!ch.active})">
                    <i class="fas fa-${ch.active ? 'pause' : 'play'}"></i> ${ch.active ? 'Desativar' : 'Ativar'}
                </button>
                <button class="btn btn-sm btn-danger" onclick="deleteChannel('${ch.id}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

function openAddChannelModal() {
    document.getElementById('channel-name').value = '';
    document.getElementById('channel-url').value = '';
    document.getElementById('channel-credentials').value = '';
    document.getElementById('channel-description').value = '';
    document.getElementById('modal-add-channel').style.display = 'flex';
    document.getElementById('channel-name').focus();
}

async function addChannel() {
    const name = document.getElementById('channel-name').value.trim();
    const channel_url = document.getElementById('channel-url').value.trim();
    const credentials_path = document.getElementById('channel-credentials').value.trim();
    const description = document.getElementById('channel-description').value.trim();

    if (!name) {
        toast('Nome do canal é obrigatório', 'error');
        return;
    }

    await api('/api/channels', 'POST', { name, channel_url, credentials_path, description });
    closeModal('modal-add-channel');
    toast('Canal adicionado!', 'success');
    fetchChannels();
}

async function toggleChannel(id, active) {
    await api(`/api/channels/${id}`, 'PATCH', { active });
    fetchChannels();
}

async function deleteChannel(id) {
    if (!confirm('Tens a certeza que queres remover este canal?')) return;
    await api(`/api/channels/${id}`, 'DELETE');
    toast('Canal removido', 'info');
    fetchChannels();
}

function clearQueueModal() {
    document.getElementById('modal-clear-queue').style.display = 'flex';
}

async function confirmClearQueue() {
    await api('/api/queue/clear', 'DELETE');
    closeModal('modal-clear-queue');
    toast('Queue limpa com sucesso!', 'success');
    fetchQueue();
}

async function testChannelPublish(channelId, channelName) {
    toast(`A testar publicação no canal "${channelName}"...`, 'info');
    const result = await api(`/api/channels/${channelId}/test-publish`, 'POST');
    if (result.error) {
        toast(`Erro: ${result.error}`, 'error');
        return;
    }
    if (result.success) {
        toast(`✅ Teste bem-sucedido! O canal "${channelName}" está pronto para publicação.`, 'success');
        return;
    }
    toast(result.message || 'Teste concluído', 'info');
}

function populateChannelSelects() {
    populateChannelSelect('video-channel');
    populateChannelSelect('setting-default-channel');
    populateChannelSelect('followed-target-channel');
}

function populateChannelSelect(selectId) {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    const currentVal = sel.value;
    // Keep first option
    const firstOpt = sel.options[0];
    sel.innerHTML = '';
    sel.appendChild(firstOpt);
    channelsData.forEach(ch => {
        const opt = document.createElement('option');
        opt.value = ch.id;
        opt.textContent = ch.name;
        sel.appendChild(opt);
    });
    sel.value = currentVal;
}

// ═══════════════════════════════════════════════
//  FOLLOWED CHANNELS (CANAIS A SEGUIR)
// ═══════════════════════════════════════════════

async function fetchFollowedChannels() {
    followedChannelsData = await api('/api/followed-channels');
    renderFollowedChannels();
}

function renderFollowedChannels() {
    const list = document.getElementById('followed-list');
    if (!list) return;

    if (!followedChannelsData || followedChannelsData.length === 0) {
        list.innerHTML = `<div class="empty-state small"><i class="fas fa-rss"></i><p>Nenhum canal fonte configurado</p></div>`;
        renderFollowedVideos([]);
        return;
    }

    list.innerHTML = followedChannelsData.map(item => {
        const targetName = getChannelName(item.target_channel_id) || 'Sem canal destino';
        return `
        <div class="followed-item ${selectedFollowedId === item.id ? 'active' : ''}" onclick="selectFollowedChannel('${item.id}')">
            <div class="followed-item-head">
                <div class="followed-item-title">${esc(item.name)}</div>
                <span class="tag ${item.active ? 'green' : 'muted'}">${item.active ? 'Ativo' : 'Pausado'}</span>
            </div>
            <div class="followed-item-url">${esc(item.source_url)}</div>
            <div class="followed-item-meta">Máx: ${item.max_age_days || 7} dias · Destino: ${esc(targetName)}</div>
            <div class="followed-item-actions">
                <button class="btn btn-sm" onclick="event.stopPropagation(); scanFollowedChannel('${item.id}')"><i class="fas fa-rotate"></i> Scan</button>
                <button class="btn btn-sm" onclick="event.stopPropagation(); toggleFollowedChannel('${item.id}', ${!item.active})"><i class="fas fa-${item.active ? 'pause' : 'play'}"></i></button>
                <button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); deleteFollowedChannel('${item.id}')"><i class="fas fa-trash"></i></button>
            </div>
        </div>`;
    }).join('');

    if (!selectedFollowedId && followedChannelsData.length > 0) {
        selectFollowedChannel(followedChannelsData[0].id);
    }
}

function selectFollowedChannel(followId) {
    selectedFollowedId = followId;
    renderFollowedChannels();
    fetchFollowedVideos(followId);
}

async function fetchFollowedVideos(followId) {
    followedVideosData = await api(`/api/followed-channels/${followId}/videos`);
    renderFollowedVideos(followedVideosData);
}

function renderFollowedVideos(videos) {
    const grid = document.getElementById('followed-videos-grid');
    const empty = document.getElementById('followed-videos-empty');
    if (!grid || !empty) return;

    if (!videos || videos.length === 0) {
        grid.innerHTML = '';
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';
    grid.innerHTML = videos.slice(0, 10).map(v => {
        const status = v.clip_status || 'not_clipped';
        const statusMap = {
            not_clipped: { cls: 'muted', icon: 'fa-circle-minus', txt: 'Sem clips' },
            queued: { cls: 'orange', icon: 'fa-clock', txt: 'Na queue' },
            done: { cls: 'green', icon: 'fa-check-circle', txt: 'Clipado' },
            error: { cls: 'red', icon: 'fa-exclamation-triangle', txt: 'Erro' },
        };
        const st = statusMap[status] || statusMap.not_clipped;

        let ageText = '';
        if (typeof v.age_days === 'number') {
            if (v.age_days === 0) ageText = 'Hoje';
            else if (v.age_days === 1) ageText = 'Há 1 dia';
            else ageText = `Há ${v.age_days} dias`;
        } else if (v.published_at) {
            ageText = new Date(v.published_at).toLocaleDateString('pt-PT');
        }

        return `
        <div class="source-video-card">
            <div class="source-video-thumb">
                <i class="fab fa-youtube"></i>
            </div>
            <div class="source-video-info">
                <div class="source-video-title" title="${esc(v.title || 'Vídeo')}">${esc(v.title || 'Vídeo')}</div>
                <div class="source-video-meta">
                    ${ageText ? `<span class="tag">${ageText}</span>` : ''}
                    <span class="tag ${st.cls}"><i class="fas ${st.icon}"></i> ${st.txt}</span>
                </div>
                <a href="${esc(v.video_url || '#')}" target="_blank" class="source-video-link">
                    <i class="fas fa-external-link-alt"></i> Ver no YouTube
                </a>
            </div>
        </div>`;
    }).join('');
}

function openAddFollowedModal() {
    populateChannelSelect('followed-target-channel');
    document.getElementById('followed-name').value = '';
    document.getElementById('followed-source-url').value = '';
    document.getElementById('followed-max-age').value = '7';
    document.getElementById('followed-target-channel').value = '';
    document.getElementById('modal-add-followed').style.display = 'flex';
}

async function addFollowedChannel() {
    const name = document.getElementById('followed-name').value.trim();
    const source_url = document.getElementById('followed-source-url').value.trim();
    const max_age_days = parseInt(document.getElementById('followed-max-age').value || '7', 10);
    const target_channel_id = document.getElementById('followed-target-channel').value || null;

    if (!name || !source_url) {
        toast('Nome e URL são obrigatórios', 'error');
        return;
    }

    const created = await api('/api/followed-channels', 'POST', {
        name,
        source_url,
        max_age_days,
        target_channel_id,
        active: true,
    });

    closeModal('modal-add-followed');
    toast('Canal fonte adicionado', 'success');
    await fetchFollowedChannels();
    if (created?.id) {
        await scanFollowedChannel(created.id);
    }
}

async function toggleFollowedChannel(id, active) {
    await api(`/api/followed-channels/${id}`, 'PATCH', { active });
    await fetchFollowedChannels();
}

async function deleteFollowedChannel(id) {
    if (!confirm('Remover este canal a seguir?')) return;
    await api(`/api/followed-channels/${id}`, 'DELETE');
    if (selectedFollowedId === id) selectedFollowedId = null;
    toast('Canal removido', 'info');
    await fetchFollowedChannels();
}

async function scanFollowedChannel(id) {
    const result = await api(`/api/followed-channels/${id}/scan`, 'POST');
    if (result.error) {
        toast(result.error, 'error');
        return;
    }
    toast(`Scan concluído: ${result.enqueued || 0} vídeos para queue`, 'success');
    await fetchQueue();
    await fetchFollowedChannels();
    if (selectedFollowedId === id) {
        await fetchFollowedVideos(id);
    }
}

async function scanAllFollowedChannels() {
    const result = await api('/api/followed-channels/scan-all', 'POST');
    const enqueuedTotal = (result || []).reduce((acc, r) => acc + (r.enqueued || 0), 0);
    toast(`Scan total: ${enqueuedTotal} vídeos para queue`, 'success');
    await fetchQueue();
    await fetchFollowedChannels();
    if (selectedFollowedId) {
        await fetchFollowedVideos(selectedFollowedId);
    }
}

// ═══════════════════════════════════════════════
//  POSTED VIDEOS
// ═══════════════════════════════════════════════

async function fetchPosted() {
    postedData = await api('/api/posted');
    renderPosted();
    updateDashboardStats();
}

function renderPosted() {
    const grid = document.getElementById('posted-grid');
    const empty = document.getElementById('posted-empty');

    if (!postedData || postedData.length === 0) {
        grid.innerHTML = '';
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';
    grid.innerHTML = postedData.map(v => {
        const channelName = getChannelName(v.channel_id);
        const date = v.published_at ? new Date(v.published_at).toLocaleDateString('pt-PT') : '';
        const youtubeUrl = v.youtube_url || v.url || '';
        return `
        <div class="posted-card">
            <div class="posted-thumbnail">
                <i class="fas fa-film"></i>
            </div>
            <div class="posted-info">
                <div class="posted-title">${esc(v.title)}</div>
                <div class="posted-channel">
                    ${channelName ? `<i class="fab fa-youtube" style="color:#ff0000"></i> ${esc(channelName)}` : ''}
                    ${date ? ` · ${date}` : ''}
                </div>
                <div class="posted-stats">
                    <span class="posted-stat views"><i class="fas fa-eye"></i> ${formatNumber(v.views || 0)}</span>
                    <span class="posted-stat likes"><i class="fas fa-heart"></i> ${formatNumber(v.likes || 0)}</span>
                    <span class="posted-stat comments"><i class="fas fa-comment"></i> ${formatNumber(v.comments || 0)}</span>
                </div>
                <div class="posted-actions">
                    ${youtubeUrl ? `<a href="${esc(youtubeUrl)}" target="_blank" class="btn btn-sm"><i class="fab fa-youtube" style="color:#ff0000"></i> Ver no YouTube</a>` : ''}
                    <button class="btn btn-sm btn-danger" onclick="deletePostedVideo('${v.id}')"><i class="fas fa-trash"></i> Apagar</button>
                </div>
            </div>
        </div>`;
    }).join('');
}

async function deletePostedVideo(id) {
    if (!confirm('Tens a certeza que queres apagar este vídeo publicado?')) return;
    await api(`/api/posted/${id}`, 'DELETE');
    toast('Vídeo removido', 'info');
    await fetchPosted();
}

// ═══════════════════════════════════════════════
//  SETTINGS
// ═══════════════════════════════════════════════

async function fetchSettings() {
    settingsData = await api('/api/settings');
    renderSettings();
}

function renderSettings() {
    if (!settingsData) return;
    document.getElementById('setting-ollama-model').value = settingsData.ollama_model || 'llama2';
    document.getElementById('setting-max-clips').value = settingsData.max_clips_per_video || 7;
    document.getElementById('setting-clip-min').value = settingsData.clip_duration_min || 30;
    document.getElementById('setting-clip-max').value = settingsData.clip_duration_max || 60;
    document.getElementById('setting-max-video-duration').value = settingsData.max_video_duration_min || 60;
    document.getElementById('setting-auto-publish').checked = settingsData.auto_publish || false;

    // Default channel
    const sel = document.getElementById('setting-default-channel');
    if (settingsData.default_channel_id) {
        sel.value = settingsData.default_channel_id;
    }
}

async function saveSettings() {
    const data = {
        ollama_model: document.getElementById('setting-ollama-model').value,
        max_clips_per_video: parseInt(document.getElementById('setting-max-clips').value) || 7,
        clip_duration_min: parseInt(document.getElementById('setting-clip-min').value) || 30,
        clip_duration_max: parseInt(document.getElementById('setting-clip-max').value) || 60,
        max_video_duration_min: parseInt(document.getElementById('setting-max-video-duration').value) || 60,
        auto_publish: document.getElementById('setting-auto-publish').checked,
        default_channel_id: document.getElementById('setting-default-channel').value || null,
    };
    await api('/api/settings', 'PATCH', data);
    toast('Definições guardadas!', 'success');
}

// ═══════════════════════════════════════════════
//  WORKER
// ═══════════════════════════════════════════════

async function fetchWorkerStatus() {
    const data = await api('/api/worker/status');
    workerRunning = data.running;
    workerPaused = data.paused;
    renderWorkerStatus();
}

function renderWorkerStatus() {
    // Sidebar indicator
    const indicator = document.getElementById('worker-status-indicator');
    if (workerRunning && !workerPaused) {
        indicator.innerHTML = '<span class="status-dot online"></span><span>Worker Ativo</span>';
    } else if (workerRunning && workerPaused) {
        indicator.innerHTML = '<span class="status-dot paused"></span><span>Worker Pausado</span>';
    } else {
        indicator.innerHTML = '<span class="status-dot offline"></span><span>Worker Parado</span>';
    }

    // Queue page button
    const btn = document.getElementById('btn-worker-toggle');
    if (btn) {
        if (workerRunning && !workerPaused) {
            btn.className = 'btn btn-danger';
            btn.innerHTML = '<i class="fas fa-stop"></i> Parar Worker';
            btn.onclick = () => stopWorker();
        } else if (workerRunning && workerPaused) {
            btn.className = 'btn btn-success';
            btn.innerHTML = '<i class="fas fa-play"></i> Retomar Worker';
            btn.onclick = () => resumeWorker();
        } else {
            btn.className = 'btn btn-success';
            btn.innerHTML = '<i class="fas fa-play"></i> Iniciar Worker';
            btn.onclick = () => startWorker();
        }
    }
}

async function toggleWorker() {
    if (workerRunning && !workerPaused) {
        await stopWorker();
    } else {
        await startWorker();
    }
}

async function startWorker() {
    await api('/api/worker/start', 'POST');
    toast('Worker iniciado!', 'success');
    fetchWorkerStatus();
}

async function stopWorker() {
    await api('/api/worker/stop', 'POST');
    toast('Worker parado', 'info');
    fetchWorkerStatus();
}

async function resumeWorker() {
    await api('/api/worker/resume', 'POST');
    toast('Worker retomado', 'success');
    fetchWorkerStatus();
}

// ═══════════════════════════════════════════════
//  CURRENT PROCESSING (Dashboard)
// ═══════════════════════════════════════════════

async function fetchCurrentProcessing() {
    const data = await api('/api/queue/current');
    renderCurrentProcessing(data);
}

function renderCurrentProcessing(item) {
    const body = document.getElementById('current-processing-body');
    if (!item || !item.id) {
        body.innerHTML = `<div class="empty-state small">
            <i class="fas fa-pause-circle"></i>
            <p>Nenhum vídeo a ser processado</p>
        </div>`;
        return;
    }

    const statusMap = {
        downloading: { icon: 'fas fa-download', label: 'A fazer download...' },
        analyzing: { icon: 'fas fa-brain', label: 'A analisar com IA...' },
        editing: { icon: 'fas fa-cut', label: 'A editar clips...' },
    };
    const st = statusMap[item.status] || { icon: 'fas fa-spinner', label: item.status };

    body.innerHTML = `
        <div class="processing-info">
            <div class="processing-icon"><i class="${st.icon}"></i></div>
            <div class="processing-details">
                <div class="processing-title">${esc(item.title)}</div>
                <div class="processing-status">
                    ${renderStatusBadge(item.status)}
                    <span style="margin-left:8px">${esc(item.status_detail || st.label)}</span>
                </div>
                <div class="processing-progress">
                    <div class="progress-bar"><div class="fill" style="width:${item.progress}%"></div></div>
                    <div class="processing-pct">${item.progress}%</div>
                </div>
            </div>
        </div>`;
}

// ═══════════════════════════════════════════════
//  DASHBOARD STATS
// ═══════════════════════════════════════════════

function updateDashboardStats() {
    const queued = queueData.filter(q => q.status === 'queued').length;
    const processing = queueData.filter(q => ['downloading', 'analyzing', 'editing'].includes(q.status)).length;
    const done = queueData.filter(q => q.status === 'done').length;
    const posted = postedData ? postedData.length : 0;

    document.getElementById('stat-queued').textContent = queued;
    document.getElementById('stat-processing').textContent = processing;
    document.getElementById('stat-done').textContent = done;
    document.getElementById('stat-posted').textContent = posted;
}

// ═══════════════════════════════════════════════
//  SYSTEM CHECKS
// ═══════════════════════════════════════════════

async function checkSystem() {
    // Show in both dashboard and settings
    const targets = ['system-checks-body', 'checks-grid'];
    targets.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted)"><i class="fas fa-spinner fa-spin"></i> A verificar...</div>';
    });

    const data = await api('/api/system/check');

    const names = {
        ffmpeg: 'FFmpeg',
        ffprobe: 'FFprobe',
        ollama: 'Ollama',
        gpu: 'GPU CUDA',
        whisper: 'Faster-Whisper',
        ytdlp: 'yt-dlp',
        disk: 'Disco',
    };
    const icons = {
        ffmpeg: 'fas fa-film',
        ffprobe: 'fas fa-search',
        ollama: 'fas fa-brain',
        gpu: 'fas fa-microchip',
        whisper: 'fas fa-microphone',
        ytdlp: 'fab fa-youtube',
        disk: 'fas fa-hdd',
    };

    let html = '';
    for (const [key, info] of Object.entries(data)) {
        html += `
        <div class="check-item">
            <div class="check-icon ${info.ok ? 'ok' : 'fail'}">
                <i class="${icons[key] || 'fas fa-check'}"></i>
            </div>
            <div class="check-info">
                <div class="check-name">${names[key] || key}</div>
                <div class="check-detail">${esc(info.detail)}</div>
            </div>
        </div>`;
    }

    targets.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = html || '<p style="color:var(--text-muted)">Sem dados</p>';
    });
}

async function checkOllama() {
    // Check Ollama status
    try {
        const data = await api('/api/system/check');
        const ollamaInfo = data.ollama;
        const statusEl = document.getElementById('ollama-status');
        if (ollamaInfo && ollamaInfo.ok) {
            statusEl.innerHTML = '<span class="status-dot online"></span><span>Ollama está a correr</span>';
        } else {
            statusEl.innerHTML = `<span class="status-dot offline"></span><span>${esc(ollamaInfo?.detail || 'Ollama não está a correr')}</span>`;
        }
    } catch {
        document.getElementById('ollama-status').innerHTML = '<span class="status-dot offline"></span><span>Erro ao verificar</span>';
    }

    // List models
    try {
        const data = await api('/api/system/ollama-models');
        const list = document.getElementById('ollama-models-list');
        if (data.ok && data.models && data.models.length > 0) {
            list.innerHTML = data.models.map(m => `<span class="tag green">${esc(m)}</span>`).join('');
        } else {
            list.innerHTML = '<span class="tag muted">Nenhum modelo instalado</span>';
        }
    } catch {
        document.getElementById('ollama-models-list').innerHTML = '<span class="tag muted">Erro ao carregar</span>';
    }
}

// ═══════════════════════════════════════════════
//  UTILS
// ═══════════════════════════════════════════════

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}

function getChannelName(id) {
    if (!id) return '';
    const ch = channelsData.find(c => c.id === id);
    return ch ? ch.name : '';
}

function formatNumber(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
}

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function toast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    const icons = { success: 'fas fa-check-circle', error: 'fas fa-exclamation-circle', info: 'fas fa-info-circle' };
    t.innerHTML = `<i class="${icons[type] || icons.info}"></i> ${msg}`;
    container.appendChild(t);
    setTimeout(() => {
        t.style.opacity = '0';
        t.style.transform = 'translateX(100%)';
        t.style.transition = 'all 0.3s ease';
        setTimeout(() => t.remove(), 300);
    }, 3500);
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.style.display = 'none';
    }
});

// Keyboard shortcut: Escape to close modals
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay').forEach(m => m.style.display = 'none');
    }
});
