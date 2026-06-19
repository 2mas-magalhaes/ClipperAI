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
let reviewSelectedIds = new Set();
let postedData = [];
let settingsData = {};
let schedulesData = {};
let workerRunning = false;
let workerPaused = false;

// ── Auto Scan ──
let nextScanTime = null;
let scanCountdownInterval = null;

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

    // Setup add video modal
    setupAddVideoModal();

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

async function refreshAll() {
    // Load channels first (needed for dropdowns in other pages)
    await fetchChannels();
    
    // Then load everything else in parallel
    await Promise.all([
        fetchQueue(),
        fetchFollowedChannels(),
        fetchReview(),
        fetchPosted(),
        fetchSettings(),
        fetchWorkerStatus(),
        fetchSchedules(),
    ]);
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
            // Inicia o countdown do scan automático
            if (!scanCountdownInterval) {
                initScanCountdown();
            }
            break;
        case 'review':
            // Ensure channels are loaded for dropdowns
            if (!channelsData || channelsData.length === 0) {
                fetchChannels().then(() => fetchReview());
            } else {
                fetchReview();
            }
            break;
        case 'posted':
            fetchPosted();
            break;
        case 'schedules':
            fetchSchedules();
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
    const text = await res.text();
    let data = {};
    try {
        data = text ? JSON.parse(text) : {};
    } catch {
        data = { ok: false, error: text || `HTTP ${res.status}` };
    }
    if (!res.ok && !data.error) {
        data.error = `HTTP ${res.status}`;
    }
    return data;
}

// ═══════════════════════════════════════════════
//  QUEUE
// ═══════════════════════════════════════════════

async function fetchQueue() {
    queueData = await api('/api/queue');
    renderQueue();
    updateDashboardStats();
}

// Queue selection state
let queueSelectedIds = new Set();

function renderQueue() {
    const tbody = document.getElementById('queue-tbody');
    const empty = document.getElementById('queue-empty');

    if (!queueData || queueData.length === 0) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        document.getElementById('queue-badge').textContent = '0';
        updateBulkBar();
        return;
    }

    empty.style.display = 'none';
    const queuedCount = queueData.filter(q => q.status === 'queued').length;
    document.getElementById('queue-badge').textContent = queuedCount || '';

    // Clean up selection: remove IDs that no longer exist
    const currentIds = new Set(queueData.map(q => q.id));
    for (const id of queueSelectedIds) {
        if (!currentIds.has(id)) queueSelectedIds.delete(id);
    }

    tbody.innerHTML = queueData.map((item, idx) => {
        const channelName = getChannelName(item.channel_id);
        const defaultChannelName = getChannelName(settingsData.default_channel_id);
        const statusBadge = renderStatusBadge(item);
        const progress = renderProgress(item);
        const clipsText = item.status === 'done'
            ? `<span style="color:var(--green)">${item.clips_done}/${item.clips_total}</span>`
            : item.clips_total > 0
                ? `${item.clips_done}/${item.clips_total}`
                : '—';

        // Duration display (in minutes)
        const durationText = item.duration_seconds 
            ? `${Math.round(item.duration_seconds / 60)}min`
            : '—';

        // Channel display with option to edit
        const channelDisplay = item.status === 'queued'
            ? (channelName 
                ? `<button class="btn btn-sm" style="padding:4px 8px;font-size:0.75rem" onclick="editQueueChannel('${item.id}')">${esc(channelName)}</button>`
                : `<button class="btn btn-sm btn-outline" style="padding:4px 8px;font-size:0.75rem" onclick="editQueueChannel('${item.id}')">Escolher canal</button>`)
            : (channelName 
                ? `<span class="tag">${esc(channelName)}</span>`
                : (defaultChannelName ? `<span class="tag" style="opacity:0.6">${esc(defaultChannelName)} (padrão)</span>` : '<span style="color:var(--text-muted)">—</span>'));

        // Privacy display
        const privacyVal = item.default_privacy || '';
        const privacyDisplay = privacyVal ? `<span class="queue-privacy-tag ${privacyVal}">${privacyVal === 'public' ? '<i class="fas fa-globe"></i>' : privacyVal === 'unlisted' ? '<i class="fas fa-eye-slash"></i>' : '<i class="fas fa-lock"></i>'}</span>` : '';

        const isSelected = queueSelectedIds.has(item.id);

        return `<tr draggable="true" data-queue-id="${item.id}" data-index="${idx}" class="${isSelected ? 'queue-row-selected' : ''}">
            <td class="queue-select-cell" onclick="event.stopPropagation()">
                <input type="checkbox" class="queue-select-cb" data-id="${item.id}" ${isSelected ? 'checked' : ''} onchange="toggleQueueSelect('${item.id}', this.checked)">
            </td>
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
                <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px"><i class="fas fa-clock"></i> ${durationText} ${privacyDisplay}</div>
            </td>
            <td>${channelDisplay}</td>
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
                <label class="auto-pub-toggle" title="Usar vídeo satisfying (desativar para estilo Opus Clips)">
                    <input type="checkbox" ${item.usar_video_satisfatorio !== false ? 'checked' : ''}
                        ${item.status !== 'queued' ? 'disabled' : ''}
                        onchange="setQueueSatisfying('${item.id}', this.checked)">
                    <span class="auto-pub-label">Sat</span>
                </label>
            </td>
            <td>
                <div style="display:flex;gap:4px">
                    ${item.status === 'queued' ? `<button class="btn btn-icon btn-sm" title="Remover" onclick="removeFromQueue('${item.id}')"><i class="fas fa-trash" style="color:var(--red)"></i></button>` : ''}
                    ${item.status === 'error' ? `<button class="btn btn-icon btn-sm" title="Tentar de novo" onclick="retryQueueItem('${item.id}')"><i class="fas fa-redo" style="color:var(--orange)"></i></button>` : ''}
                    ${item.status === 'done' ? `<button class="btn btn-icon btn-sm" title="Ver clips" onclick="showClips('${item.id}')"><i class="fas fa-film" style="color:var(--green)"></i></button>` : ''}
                    ${['downloading', 'analyzing', 'editing'].includes(item.status) ? `<button class="btn btn-icon btn-sm" title="Abortar" onclick="cancelQueueItem('${item.id}')"><i class="fas fa-stop-circle" style="color:var(--red)"></i></button>` : ''}
                </div>
            </td>
        </tr>`;
    }).join('');
    
    // Setup drag-and-drop handlers
    setupQueueDragAndDrop();
    updateBulkBar();
}

// === DRAG AND DROP ===
let draggedElement = null;
let dragOverElement = null;
let insertAfter = false;
let dragIndicator = null;
let dragIndicatorAdded = false;

function setupQueueDragAndDrop() {
    const tbody = document.getElementById('queue-tbody');
    if (!tbody) return;

    // Create reusable drag indicator element
    if (!dragIndicator) {
        dragIndicator = document.createElement('tr');
        dragIndicator.id = 'drag-indicator';
        dragIndicator.innerHTML = '<td colspan="99" style="height:3px;padding:0;background:var(--blue);border:none;box-shadow:0 0 8px var(--blue);"></td>';
        dragIndicator.style.display = 'none';
    }

    // Use event delegation on tbody for robustness
    tbody.addEventListener('dragstart', e => {
        const row = e.target.closest('tr[draggable="true"]');
        if (!row) return;
        draggedElement = row;
        draggedElement.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', row.dataset.queueId);
        e.dataTransfer.dropEffect = 'move';
        dragIndicatorAdded = false;
    }, false);

    tbody.addEventListener('dragover', e => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        
        if (!draggedElement) return;
        
        const row = e.target.closest('tr[draggable="true"]');
        if (!row || row === draggedElement) return;

        // Determine if we're in top or bottom half
        const rect = row.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        insertAfter = e.clientY >= midY;

        // Update visual indicator
        if (dragOverElement !== row) {
            if (dragOverElement) dragOverElement.classList.remove('drag-over');
            dragOverElement = row;
            row.classList.add('drag-over');
        }
        
        // Remove indicator if it exists
        if (dragIndicatorAdded && dragIndicator.parentNode) {
            dragIndicator.parentNode.removeChild(dragIndicator);
            dragIndicatorAdded = false;
        }
        
        // Position indicator
        if (insertAfter) {
            tbody.insertBefore(dragIndicator, row.nextSibling);
        } else {
            tbody.insertBefore(dragIndicator, row);
        }
        dragIndicator.style.display = '';
        dragIndicatorAdded = true;
    }, false);

    tbody.addEventListener('dragleave', e => {
        if (!tbody.contains(e.relatedTarget)) {
            if (dragOverElement) dragOverElement.classList.remove('drag-over');
            dragOverElement = null;
            if (dragIndicatorAdded && dragIndicator.parentNode) {
                dragIndicator.parentNode.removeChild(dragIndicator);
                dragIndicatorAdded = false;
            }
        }
    }, false);

    tbody.addEventListener('drop', e => {
        e.preventDefault();
        e.stopPropagation();
        
        // Move the element if valid
        if (dragOverElement && draggedElement && dragOverElement !== draggedElement) {
            if (insertAfter) {
                dragOverElement.parentNode.insertBefore(draggedElement, dragOverElement.nextSibling);
            } else {
                dragOverElement.parentNode.insertBefore(draggedElement, dragOverElement);
            }
        }
        
        // Clean up indicator
        if (dragIndicatorAdded && dragIndicator.parentNode) {
            dragIndicator.parentNode.removeChild(dragIndicator);
            dragIndicatorAdded = false;
        }
        if (dragOverElement) dragOverElement.classList.remove('drag-over');
        dragOverElement = null;

        const newOrder = Array.from(tbody.querySelectorAll('tr[data-queue-id]'))
            .map(row => row.dataset.queueId);
        reorderQueue(newOrder);
    }, false);

    tbody.addEventListener('dragend', e => {
        if (draggedElement) draggedElement.classList.remove('dragging');
        if (dragOverElement) dragOverElement.classList.remove('drag-over');
        if (dragIndicatorAdded && dragIndicator.parentNode) {
            dragIndicator.parentNode.removeChild(dragIndicator);
            dragIndicatorAdded = false;
        }
        draggedElement = null;
        dragOverElement = null;
    }, false);
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

function renderStatusBadge(item) {
    const status = typeof item === 'string' ? item : item.status;
    const autoPublish = typeof item === 'object' ? item.auto_publish : false;

    // If done and auto_publish, show "A publicar" state
    if (status === 'done' && autoPublish) {
        return `<span class="status-badge publishing"><i class="fas fa-upload"></i> A publicar</span>`;
    }

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

async function setQueueSatisfying(id, value) {
    await api(`/api/queue/${id}`, 'PATCH', { usar_video_satisfatorio: value });
    const item = queueData.find(q => q.id === id);
    if (item) item.usar_video_satisfatorio = value;
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

async function cancelQueueItem(id) {
    if (!confirm('Tens a certeza que queres cancelar este vídeo?')) return;
    const result = await api(`/api/queue/${id}/cancel`, 'POST');
    if (result.error) {
        toast(result.error, 'error');
        return;
    }
    // Remove o item da queue
    await removeFromQueue(id);
    toast('Vídeo cancelado e removido', 'success');
}

async function editQueueChannel(id) {
    const item = queueData.find(q => q.id === id);
    if (!item) return;
    
    // Ensure channels are loaded before showing modal
    if (!channelsData || channelsData.length === 0) {
        await fetchChannels();
    }
    
    // Create a simple dropdown menu
    const currentChannel = item.channel_id || settingsData.default_channel_id;
    const currentChannelName = getChannelName(currentChannel);
    
    const options = channelsData.map(ch => `
        <option value="${ch.id}" ${currentChannel === ch.id ? 'selected' : ''}>${esc(ch.name)}</option>
    `).join('');
    
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h3>Escolher Canal para "${esc(item.title.substring(0, 40))}"</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Canal de Publicação</label>
                    <select id="temp-channel-select" class="form-control">
                        <option value="">— Usar canal padrão —</option>
                        ${options}
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
                <button class="btn btn-primary" onclick="saveQueueChannel('${id}', document.getElementById('temp-channel-select').value); this.closest('.modal-overlay').remove()">Guardar</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    document.getElementById('temp-channel-select').focus();
}

async function saveQueueChannel(id, channelId) {
    await api(`/api/queue/${id}`, 'PATCH', { channel_id: channelId || null });
    const item = queueData.find(q => q.id === id);
    if (item) item.channel_id = channelId || null;
    toast('Canal atualizado', 'success');
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
//  QUEUE BULK ACTIONS
// ═══════════════════════════════════════════════

function toggleQueueSelect(id, checked) {
    if (checked) {
        queueSelectedIds.add(id);
    } else {
        queueSelectedIds.delete(id);
    }
    // Update row highlight
    const row = document.querySelector(`tr[data-queue-id="${id}"]`);
    if (row) row.classList.toggle('queue-row-selected', checked);
    updateBulkBar();
}

function toggleSelectAllQueue(checked) {
    queueSelectedIds.clear();
    if (checked) {
        queueData.forEach(item => queueSelectedIds.add(item.id));
    }
    // Update all checkboxes
    document.querySelectorAll('.queue-select-cb').forEach(cb => {
        cb.checked = checked;
        const row = cb.closest('tr');
        if (row) row.classList.toggle('queue-row-selected', checked);
    });
    updateBulkBar();
}

function updateBulkBar() {
    const bar = document.getElementById('queue-bulk-bar');
    const countEl = document.getElementById('bulk-selected-count');
    const headerCb = document.getElementById('queue-select-all-head');
    if (!bar) return;

    const count = queueSelectedIds.size;
    if (count > 0) {
        bar.style.display = 'flex';
        countEl.textContent = count;
    } else {
        bar.style.display = 'none';
    }

    // Update header checkbox state
    if (headerCb && queueData) {
        if (count === 0) {
            headerCb.checked = false;
            headerCb.indeterminate = false;
        } else if (count === queueData.length) {
            headerCb.checked = true;
            headerCb.indeterminate = false;
        } else {
            headerCb.checked = false;
            headerCb.indeterminate = true;
        }
    }
}

function getSelectedQueueIds() {
    return Array.from(queueSelectedIds);
}

async function bulkQueueAction(action, params = {}) {
    const ids = getSelectedQueueIds();
    if (ids.length === 0) return;

    try {
        const result = await api('/api/queue/bulk', 'POST', { ids, action, ...params });
        if (result.error) {
            toast(result.error, 'error');
            return;
        }
        toast(result.message || 'Ação aplicada', 'success');
        queueSelectedIds.clear();
        fetchQueue();
    } catch (e) {
        toast('Erro na ação em massa', 'error');
    }
}

async function bulkSetChannel() {
    const ids = getSelectedQueueIds();
    if (ids.length === 0) return;

    // Ensure channels are loaded before showing modal
    if (!channelsData || channelsData.length === 0) {
        await fetchChannels();
    }

    const options = channelsData.map(ch => `
        <option value="${ch.id}">${esc(ch.name)}</option>
    `).join('');

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h3>Alterar Canal — ${ids.length} vídeo(s)</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Canal de Publicação</label>
                    <select id="bulk-channel-select" class="form-control">
                        <option value="">— Usar canal padrão —</option>
                        ${options}
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
                <button class="btn btn-primary" onclick="confirmBulkChannel(this)">Aplicar</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

async function confirmBulkChannel(btn) {
    const channelId = document.getElementById('bulk-channel-select').value;
    btn.closest('.modal-overlay').remove();
    await bulkQueueAction('set_channel', { channel_id: channelId || null });
}

async function bulkInterlaceChannels() {
    const ids = getSelectedQueueIds();
    if (ids.length === 0) return;

    // Ensure channels are loaded
    if (!channelsData || channelsData.length === 0) {
        await fetchChannels();
    }

    if (channelsData.length === 0) {
        toast('Nenhum canal disponível', 'error');
        return;
    }

    if (channelsData.length === 1) {
        toast('Tens apenas 1 canal. Intercalar requer 2+ canais.', 'warning');
        return;
    }

    // Show confirmation modal
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h3>Intercalar Canais — ${ids.length} vídeo(s)</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <p>Os vídeos selecionados serão distribuídos alternadamente entre os ${channelsData.length} canais:</p>
                <ul style="margin:12px 0;padding-left:20px">
                    ${channelsData.map((ch, i) => `<li><strong>${esc(ch.name)}</strong> (vídeos ${getInterlacePattern(i, channelsData.length, ids.length)})</li>`).join('')}
                </ul>
                <p style="margin-top:12px;color:var(--text-muted);font-size:0.9rem">
                    <i class="fas fa-info-circle"></i> Ordem: Canal 1 → Canal 2 → ... → Canal ${channelsData.length} → Canal 1 ...
                </p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
                <button class="btn btn-primary" onclick="confirmInterlaceChannels(this)">Aplicar</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function getInterlacePattern(channelIndex, totalChannels, totalVideos) {
    // Calculate which video numbers will get this channel (1-based)
    const positions = [];
    for (let i = channelIndex + 1; i <= totalVideos; i += totalChannels) {
        positions.push(i);
        if (positions.length >= 6) {  // Limit display to first 6
            positions.push('...');
            break;
        }
    }
    return positions.join(', ');
}

async function confirmInterlaceChannels(btn) {
    btn.closest('.modal-overlay').remove();
    await bulkQueueAction('interlace_channels');
}

function bulkSetPrivacy() {
    const ids = getSelectedQueueIds();
    if (ids.length === 0) return;

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h3>Alterar Visibilidade — ${ids.length} vídeo(s)</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Visibilidade</label>
                    <select id="bulk-privacy-select" class="form-control">
                        <option value="public">Público</option>
                        <option value="unlisted">Não listado</option>
                        <option value="private">Privado</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
                <button class="btn btn-primary" onclick="confirmBulkPrivacy(this)">Aplicar</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

async function confirmBulkPrivacy(btn) {
    const privacy = document.getElementById('bulk-privacy-select').value;
    btn.closest('.modal-overlay').remove();
    await bulkQueueAction('set_privacy', { default_privacy: privacy });
}

async function bulkSetAutoPublish(value) {
    await bulkQueueAction('set_auto_publish', { auto_publish: value });
}

async function bulkRetry() {
    const ids = getSelectedQueueIds();
    if (ids.length === 0) return;
    if (!confirm(`Tentar de novo ${ids.length} vídeo(s)?`)) return;
    await bulkQueueAction('retry');
}

async function bulkDelete() {
    const ids = getSelectedQueueIds();
    if (ids.length === 0) return;
    if (!confirm(`Tens a certeza que queres remover ${ids.length} vídeo(s) da queue?`)) return;
    await bulkQueueAction('delete');
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

    const pending = (reviewData || []).filter(c => c.status === 'pending' || c.status === 'uploading');

    // Keep only valid selected IDs from current pending list.
    const currentPendingIds = new Set(pending.map(c => c.id));
    for (const id of reviewSelectedIds) {
        if (!currentPendingIds.has(id)) reviewSelectedIds.delete(id);
    }

    if (pending.length === 0) {
        grid.innerHTML = '';
        empty.style.display = 'block';
        updateReviewBulkBar();
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
        const isUploading = clip.status === 'uploading';
        const isSelected = reviewSelectedIds.has(clip.id);
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
        <div class="review-card ${isUploading ? 'publishing' : ''} ${isSelected ? 'review-card-selected' : ''}" data-clip-id="${clip.id}">
            <label class="review-select-corner" title="Selecionar clip" onclick="event.stopPropagation()">
                <input type="checkbox" class="review-select-cb" ${isSelected ? 'checked' : ''} ${isUploading ? 'disabled' : ''} onchange="toggleReviewSelect('${clip.id}', this.checked)">
            </label>
            <video class="review-video" controls preload="metadata" src="${esc(clipUrl)}"></video>
            <div class="review-content">
                <div class="review-title">${esc(youtubeTitle)}</div>
                <div class="review-meta">
                    ${channelName ? `<span class="tag">${esc(channelName)}</span>` : '<span class="tag muted">Sem canal</span>'}
                    ${isUploading ? '<span class="tag uploading-tag"><i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> A publicar</span>' : ''}
                    ${clip.reason ? `<span class="text-muted">${esc(clip.reason)}</span>` : ''}
                </div>
                ${sourceBlock}
                
                <!-- Descrição e Hashtags -->
                <div class="review-description-section" style="margin-top:12px">
                    <details style="cursor:pointer">
                        <summary style="font-weight:500;color:var(--text-primary);padding:8px 0"><i class="fas fa-align-left"></i> Descrição (com hashtags)</summary>
                        <div style="margin-top:8px;padding:10px;background:var(--bg-input);border-radius:6px;font-size:0.85rem;color:var(--text-secondary);line-height:1.6;white-space:pre-wrap;word-wrap:break-word;max-height:250px;overflow-y:auto">
                            ${clip.youtube && clip.youtube.descricao ? esc(clip.youtube.descricao) : '(sem descrição)'}
                        </div>
                    </details>
                </div>
                
                <div class="form-group" style="margin-top:10px">
                    <label>Canal para publicar</label>
                    <select class="form-control" onchange="setReviewChannel('${clip.id}', this.value)" ${isUploading ? 'disabled' : ''}>
                        <option value="">— Selecionar canal —</option>
                        ${channelsData.map(ch => `<option value="${ch.id}" ${clip.channel_id === ch.id ? 'selected' : ''}>${esc(ch.name)}</option>`).join('')}
                    </select>
                </div>
                <div class="review-actions">
                    ${isUploading
                        ? `<div class="publishing-indicator"><i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> A publicar no YouTube...</div>`
                        : `<button class="btn btn-success" onclick="publishReviewClip('${clip.id}')">
                            <i class="fas fa-upload"></i> Publicar
                          </button>
                          <button class="btn btn-danger" onclick="rejectReviewClip('${clip.id}')">
                            <i class="fas fa-times"></i> Rejeitar
                          </button>`
                    }
                </div>
            </div>
        </div>`;
    }).join('');

    updateReviewBulkBar();
}

function toggleReviewSelect(id, checked) {
    if (checked) reviewSelectedIds.add(id);
    else reviewSelectedIds.delete(id);

    const card = document.querySelector(`.review-card[data-clip-id="${id}"]`);
    if (card) card.classList.toggle('review-card-selected', checked);
    updateReviewBulkBar();
}

function toggleSelectAllReview(checked) {
    reviewSelectedIds.clear();
    if (checked) {
        for (const clip of (reviewData || [])) {
            if (clip.status === 'pending') reviewSelectedIds.add(clip.id);
        }
    }
    renderReview();
}

function getSelectedReviewIds() {
    return Array.from(reviewSelectedIds);
}

function updateReviewBulkBar() {
    const bar = document.getElementById('review-bulk-bar');
    const countEl = document.getElementById('review-bulk-selected-count');
    const selectAll = document.getElementById('review-select-all');
    if (!bar || !countEl || !selectAll) return;

    const pendingCount = (reviewData || []).filter(c => c.status === 'pending').length;
    const selectedCount = reviewSelectedIds.size;

    bar.style.display = pendingCount > 0 ? 'flex' : 'none';
    countEl.textContent = selectedCount;

    if (selectedCount === 0) {
        selectAll.checked = false;
        selectAll.indeterminate = false;
    } else if (selectedCount === pendingCount) {
        selectAll.checked = true;
        selectAll.indeterminate = false;
    } else {
        selectAll.checked = false;
        selectAll.indeterminate = true;
    }
}

async function bulkReviewSetChannel() {
    const ids = getSelectedReviewIds();
    if (ids.length === 0) return;

    if (!channelsData || channelsData.length === 0) await fetchChannels();
    if (!channelsData || channelsData.length === 0) {
        toast('Nenhum canal disponível', 'error');
        return;
    }

    const options = channelsData.map(ch => `<option value="${ch.id}">${esc(ch.name)}</option>`).join('');
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h3>Alterar Canal — ${ids.length} clip(s)</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()"><i class="fas fa-times"></i></button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Canal de Publicação</label>
                    <select id="bulk-review-channel-select" class="form-control">
                        <option value="">— Selecionar canal —</option>
                        ${options}
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
                <button class="btn btn-primary" onclick="confirmBulkReviewSetChannel(this)">Aplicar</button>
            </div>
        </div>`;
    document.body.appendChild(modal);
}

async function confirmBulkReviewSetChannel(btn) {
    const channelId = document.getElementById('bulk-review-channel-select').value;
    if (!channelId) {
        toast('Seleciona um canal', 'warning');
        return;
    }
    btn.closest('.modal-overlay').remove();

    const ids = getSelectedReviewIds();
    for (const clipId of ids) {
        await api(`/api/review/${clipId}`, 'PATCH', { channel_id: channelId });
    }
    toast(`Canal aplicado a ${ids.length} clip(s)`, 'success');
    await fetchReview();
}

async function bulkReviewInterlaceChannels() {
    const ids = getSelectedReviewIds();
    if (ids.length === 0) return;

    if (!channelsData || channelsData.length === 0) await fetchChannels();
    if (!channelsData || channelsData.length < 2) {
        toast('Intercalar requer pelo menos 2 canais', 'warning');
        return;
    }

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h3>Intercalar Canais — ${ids.length} clip(s)</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()"><i class="fas fa-times"></i></button>
            </div>
            <div class="modal-body">
                <p>Os clips selecionados vão ser distribuídos alternadamente pelos canais:</p>
                <ul style="margin:10px 0 0 18px;line-height:1.5">
                    ${channelsData.map(ch => `<li>${esc(ch.name)}</li>`).join('')}
                </ul>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
                <button class="btn btn-primary" onclick="confirmBulkReviewInterlace(this)">Aplicar</button>
            </div>
        </div>`;
    document.body.appendChild(modal);
}

async function confirmBulkReviewInterlace(btn) {
    btn.closest('.modal-overlay').remove();
    const ids = getSelectedReviewIds();
    if (ids.length === 0) return;

    // Keep visual order from current pending list.
    const ordered = (reviewData || []).filter(c => ids.includes(c.id) && c.status === 'pending');
    for (let i = 0; i < ordered.length; i++) {
        const clip = ordered[i];
        const channel = channelsData[i % channelsData.length];
        await api(`/api/review/${clip.id}`, 'PATCH', { channel_id: channel.id });
    }

    toast(`Intercalado por ${channelsData.length} canais`, 'success');
    await fetchReview();
}

async function bulkRejectReviewClips() {
    const ids = getSelectedReviewIds();
    if (ids.length === 0) return;
    if (!confirm(`Rejeitar ${ids.length} clip(s) selecionados?`)) return;

    let rejected = 0;
    let failed = 0;
    for (const id of ids) {
        try {
            await api(`/api/review/${id}`, 'DELETE');
            rejected += 1;
        } catch (_) {
            failed += 1;
        }
    }

    reviewSelectedIds.clear();
    await fetchReview();
    toast(`Rejeitados: ${rejected}${failed ? `, falhas: ${failed}` : ''}`, failed ? 'warning' : 'success');
}

async function bulkPublishReviewClips() {
    const ids = getSelectedReviewIds();
    if (ids.length === 0) return;
    if (!confirm(`Publicar ${ids.length} clip(s) selecionados?`)) return;

    let success = 0;
    let failed = 0;

    for (const id of ids) {
        const clip = reviewData.find(c => c.id === id);
        if (!clip || clip.status !== 'pending') continue;

        const card = document.querySelector(`.review-card[data-clip-id="${id}"]`);
        if (card) card.classList.add('publishing');

        try {
            const result = await api(`/api/review/${id}/publish`, 'POST', { channel_id: clip.channel_id || null });
            if (result && result.success) success += 1;
            else failed += 1;
        } catch (_) {
            failed += 1;
        }
    }

    reviewSelectedIds.clear();
    await fetchReview();
    await fetchPosted();
    await fetchChannels();
    toast(`Publicados: ${success}${failed ? `, falhas: ${failed}` : ''}`, failed ? 'warning' : 'success');
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

    // Ler o canal diretamente do dropdown (fonte de verdade) em vez de depender de reviewData
    const card = document.querySelector(`.review-card[data-clip-id="${clipId}"]`);
    const channelSelect = card ? card.querySelector('select.form-control') : null;
    const selectedChannelId = channelSelect ? channelSelect.value : (clip.channel_id || null);
    
    // Atualizar reviewData e BD se o dropdown tiver valor diferente
    if (selectedChannelId !== (clip.channel_id || '')) {
        clip.channel_id = selectedChannelId || null;
        // Guardar no servidor sem bloquear
        api(`/api/review/${clipId}`, 'PATCH', { channel_id: selectedChannelId || null });
    }

    // Abre modal de publicação com logs
    openPublishLogModal(clip);

    const logsEl = document.getElementById('publish-logs');
    const resultEl = document.getElementById('publish-result');
    const btn = document.getElementById('publish-close-btn');

    if (logsEl) {
        logsEl.innerHTML = '<div class="log-line log-info"><i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> A iniciar publicação...</div>';
    }
    if (btn) btn.disabled = true;

    // Marcar card como "a publicar"
    if (card) {
        card.classList.add('publishing');
        const actionsEl = card.querySelector('.review-actions');
        if (actionsEl) {
            actionsEl.innerHTML = `
                <div class="publishing-indicator">
                    <i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i>
                    <span>A publicar no YouTube...</span>
                </div>`;
        }
    }

    try {
        const result = await api(`/api/review/${clipId}/publish`, 'POST', { channel_id: selectedChannelId || null });
        const logs = result.logs || [];

        if (logsEl) {
            logsEl.innerHTML = logs.map(line => {
                if (!line.trim()) return '<div class="log-line log-empty">&nbsp;</div>';
                if (line.startsWith('===')) return `<div class="log-line log-header">${esc(line)}</div>`;
                if (line.startsWith('[')) return `<div class="log-line log-step">${esc(line)}</div>`;
                if (line.startsWith('OK')) return `<div class="log-line log-ok"><i class="fas fa-check"></i> ${esc(line.substring(5))}</div>`;
                if (line.startsWith('FALHOU')) return `<div class="log-line log-fail"><i class="fas fa-times"></i> ${esc(line.substring(9))}</div>`;
                if (line.startsWith('AVISO')) return `<div class="log-line log-warn"><i class="fas fa-exclamation-triangle"></i> ${esc(line.substring(8))}</div>`;
                if (line.startsWith('Upload:')) return `<div class="log-line log-progress"><i class="fas fa-cloud-upload-alt"></i> ${esc(line)}</div>`;
                if (line.startsWith('→')) return `<div class="log-line log-hint">${esc(line)}</div>`;
                return `<div class="log-line">${esc(line)}</div>`;
            }).join('');
            logsEl.scrollTop = logsEl.scrollHeight;
        }

        if (resultEl) {
            if (result.success) {
                const ytUrl = result.youtube_url || '';
                resultEl.innerHTML = `
                    <div class="test-result-ok">
                        <i class="fas fa-check-circle"></i> Publicado com sucesso!
                        ${ytUrl ? `<a href="${esc(ytUrl)}" target="_blank" class="btn btn-sm" style="margin-left:12px"><i class="fab fa-youtube"></i> Ver no YouTube</a>` : ''}
                    </div>`;
            } else {
                resultEl.innerHTML = `<div class="test-result-fail"><i class="fas fa-times-circle"></i> ${esc(result.error || 'Falha na publicação')}</div>`;
            }
            resultEl.style.display = 'block';
        }

        if (result.success) {
            toast('Clip publicado com sucesso!', 'success');
        } else {
            toast(result.error || 'Erro na publicação', 'error');
        }
    } catch (err) {
        if (logsEl) {
            logsEl.innerHTML = `<div class="log-line log-fail"><i class="fas fa-times"></i> Erro de comunicação: ${esc(err.message || String(err))}</div>`;
        }
        if (resultEl) {
            resultEl.innerHTML = `<div class="test-result-fail"><i class="fas fa-times-circle"></i> Erro de comunicação com o servidor</div>`;
            resultEl.style.display = 'block';
        }
        toast('Erro ao publicar', 'error');
    } finally {
        if (btn) btn.disabled = false;
        await fetchReview();
        await fetchPosted();
        await fetchChannels();
    }
}

function openPublishLogModal(clip) {
    const old = document.getElementById('modal-publish-log');
    if (old) old.remove();

    const title = clip.youtube?.titulo || clip.title || 'Clip';

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'modal-publish-log';
    modal.innerHTML = `
        <div class="modal modal-lg">
            <div class="modal-header">
                <h3><i class="fas fa-upload"></i> A Publicar — ${esc(title)}</h3>
                <button class="modal-close" onclick="document.getElementById('modal-publish-log').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="test-publish-logs" id="publish-logs">
                    <div class="log-line log-info"><i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> A preparar publicação...</div>
                </div>
                <div class="test-publish-result" id="publish-result" style="display:none"></div>
            </div>
            <div class="modal-footer">
                <button class="btn" id="publish-close-btn" onclick="document.getElementById('modal-publish-log').remove()">Fechar</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
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
    document.getElementById('video-file-title').value = '';
    document.getElementById('video-file').value = '';
    document.getElementById('video-origin-url').value = '';
    document.getElementById('file-name-display').style.display = 'none';
    document.getElementById('video-origin-info').style.display = 'none';
    document.getElementById('video-origin-status').textContent = 'Cole a URL original para auto-preencher nome, canal e descrição';
    window.videoOriginData = null; // Reset origin data
    // Reset para aba YouTube
    document.getElementById('tab-youtube-content').style.display = 'block';
    document.getElementById('tab-file-content').style.display = 'none';
    document.getElementById('tab-youtube-btn').style.borderBottomColor = 'var(--primary)';
    document.getElementById('tab-youtube-btn').style.color = 'var(--primary)';
    document.getElementById('tab-file-btn').style.borderBottomColor = 'transparent';
    document.getElementById('tab-file-btn').style.color = 'inherit';
    // Pre-preenche o checkbox com o valor global
    document.getElementById('video-auto-publish').checked = settingsData.auto_publish || false;
    document.getElementById('video-usar-video-satisfatorio').checked = settingsData.usar_video_satisfatorio !== false;
    document.getElementById('modal-add-video').style.display = 'flex';
    document.getElementById('video-url').focus();
}

async function addVideoToQueue() {
    const activeTab = document.getElementById('tab-youtube-content').style.display !== 'none' ? 'youtube' : 'file';
    
    if (activeTab === 'youtube') {
        await addVideoYoutube();
    } else {
        await addVideoFromFile();
    }
}

async function addVideoYoutube() {
    const url = document.getElementById('video-url').value.trim();
    const title = document.getElementById('video-title').value.trim();
    const channelId = document.getElementById('video-channel').value;
    const autoPublish = document.getElementById('video-auto-publish').checked;
    const usarVideoSatisfatorio = document.getElementById('video-usar-video-satisfatorio').checked;

    if (!url) {
        toast('URL é obrigatória', 'error');
        return;
    }

    await api('/api/queue', 'POST', {
        url,
        title,
        channel_id: channelId || null,
        auto_publish: autoPublish,
        usar_video_satisfatorio: usarVideoSatisfatorio,
    });
    closeModal('modal-add-video');
    toast('Vídeo adicionado à queue!', 'success');
    fetchQueue();
}

async function addVideoFromFile() {
    const fileInput = document.getElementById('video-file');
    const title = document.getElementById('video-file-title').value.trim();
    const channelId = document.getElementById('video-channel').value;
    const autoPublish = document.getElementById('video-auto-publish').checked;
    const usarVideoSatisfatorio = document.getElementById('video-usar-video-satisfatorio').checked;

    if (!fileInput.files || !fileInput.files[0]) {
        toast('Selecione um ficheiro de vídeo', 'error');
        return;
    }

    if (!title) {
        toast('Título é obrigatório', 'error');
        return;
    }

    const file = fileInput.files[0];
    const maxSize = 4 * 1024 * 1024 * 1024; // 4GB
    
    if (file.size > maxSize) {
        toast(`Ficheiro muito grande. Máximo é 4GB (seu ficheiro: ${(file.size / (1024*1024*1024)).toFixed(2)}GB)`, 'error');
        return;
    }

    // Upload com progress
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('channel_id', channelId || null);
    formData.append('auto_publish', autoPublish ? '1' : '0');
    formData.append('usar_video_satisfatorio', usarVideoSatisfatorio ? '1' : '0');
    
    // Add origin data if available
    if (window.videoOriginData) {
        formData.append('origin_title', window.videoOriginData.title);
        formData.append('origin_url', window.videoOriginData.url);
        formData.append('origin_channel_name', window.videoOriginData.channel_name);
        formData.append('origin_channel_url', window.videoOriginData.channel_url);
    }

    try {
        const btn = document.getElementById('btn-add-video');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> A enviar...';

        const response = await fetch('/api/queue/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Erro ao fazer upload');
        }

        closeModal('modal-add-video');
        toast('Vídeo enviado e adicionado à queue!', 'success');
        document.getElementById('video-file').value = '';
        document.getElementById('file-name-display').style.display = 'none';
        document.getElementById('video-file-title').value = '';
        fetchQueue();
    } catch (error) {
        toast(`Erro: ${error.message}`, 'error');
    } finally {
        const btn = document.getElementById('btn-add-video');
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-plus"></i> Adicionar';
    }
}

// ═══════════════════════════════════════════════
//  CHANNELS
// ═══════════════════════════════════════════════

async function fetchChannels() {
    channelsData = await api('/api/channels');
    renderChannels();
    populateChannelSelects();
    
    // Re-render review if it's the current page (to update channel dropdowns)
    if (currentPage === 'review') {
        renderReview();
    }
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
    grid.innerHTML = channelsData.map(ch => {
        const hasThumb = ch.channel_thumbnail && ch.channel_thumbnail.length > 10;
        const hasCredentials = ch.credentials_path && ch.credentials_path.trim().length > 0;
        const ytName = ch.youtube_channel_name || '';
        const ytSubs = ch.youtube_subscribers || '';
        const ytVideos = ch.youtube_video_count || ch.videos_posted || 0;
        const ytViews = ch.youtube_view_count || ch.total_views || 0;

        return `
        <div class="channel-card ${!ch.active ? 'channel-inactive' : ''}">
            <div class="channel-card-top">
                ${ch.active ? '<span class="channel-badge">Ativo</span>' : '<span class="channel-badge channel-badge-off">Inativo</span>'}
                <button class="channel-settings-btn" onclick="event.stopPropagation();openChannelSettingsModal('${ch.id}')" title="Definições do canal">
                    <i class="fas fa-cog"></i>
                </button>
            </div>
            <div class="channel-header channel-header-clickable" onclick="openChannelDetailModal('${ch.id}')">
                ${hasThumb
                    ? `<img class="channel-avatar-img" src="${esc(ch.channel_thumbnail)}" alt="${esc(ch.name)}" onerror="this.nextElementSibling.style.display='flex';this.style.display='none'">`
                    : ''}
                <div class="channel-avatar" ${hasThumb ? 'style="display:none"' : ''}><i class="fab fa-youtube"></i></div>
                <div class="channel-header-text">
                    <div class="channel-name">${esc(ch.name)}</div>
                    ${ytName && ytName !== ch.name ? `<div class="channel-yt-name">${esc(ytName)}</div>` : ''}
                    <div class="channel-url">${esc(ch.channel_url || 'Sem URL configurada')}</div>
                    ${ytSubs ? `<div class="channel-subs"><i class="fas fa-users"></i> ${formatNumber(parseInt(ytSubs))} subscritores</div>` : ''}
                </div>
                <i class="fas fa-chevron-right channel-detail-arrow"></i>
            </div>
            <div class="channel-stats">
                <div class="channel-stat">
                    <div class="val">${formatNumber(parseInt(ytVideos) || 0)}</div>
                    <div class="lbl">Vídeos</div>
                </div>
                <div class="channel-stat">
                    <div class="val">${formatNumber(parseInt(ytViews) || 0)}</div>
                    <div class="lbl">Views</div>
                </div>
                <div class="channel-stat">
                    <div class="val">${formatNumber(parseInt(ytSubs) || 0)}</div>
                    <div class="lbl">Subs</div>
                </div>
            </div>
            <div class="channel-connection-status">
                ${hasCredentials
                    ? `<div class="conn-ok"><i class="fas fa-link"></i> OAuth configurado</div>`
                    : `<div class="conn-missing"><i class="fas fa-unlink"></i> Sem credenciais OAuth</div>`
                }
            </div>
            <div class="channel-actions">
                <button class="btn btn-sm" onclick="openTestPublishModal('${ch.id}')">
                    <i class="fas fa-flask"></i> Testar
                </button>
                <button class="btn btn-sm" onclick="reauthChannel('${ch.id}')" title="Iniciar sessão com outra conta Google">
                    <i class="fas fa-key"></i> Trocar Conta
                </button>
                <button class="btn btn-sm" onclick="toggleChannel('${ch.id}', ${!ch.active})">
                    <i class="fas fa-${ch.active ? 'pause' : 'play'}"></i> ${ch.active ? 'Desativar' : 'Ativar'}
                </button>
                <button class="btn btn-sm btn-danger" onclick="deleteChannel('${ch.id}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>`;
    }).join('');
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

    // Botão de loading enquanto busca avatar
    const addBtn = document.querySelector('#modal-add-channel .btn-primary');
    if (addBtn) {
        addBtn.disabled = true;
        addBtn.innerHTML = '<i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> A adicionar...';
    }

    try {
        const ch = await api('/api/channels', 'POST', { name, channel_url, credentials_path, description });
        closeModal('modal-add-channel');
        toast('Canal adicionado!', 'success');
        await fetchChannels();

        // Se tem credenciais, abre automaticamente o teste OAuth
        if (credentials_path && ch && ch.id) {
            openTestPublishModal(ch.id);
        }
    } catch (err) {
        toast('Erro ao adicionar canal', 'error');
    } finally {
        if (addBtn) {
            addBtn.disabled = false;
            addBtn.innerHTML = '<i class="fas fa-plus"></i> Adicionar Canal';
        }
    }
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

async function reauthChannel(channelId) {
    if (!confirm('Vai abrir o browser para iniciar sessão com outra conta Google.\n\nContinuar?')) return;
    toast('🔑 A abrir janela de autenticação...', 'info');
    try {
        const result = await api(`/api/channels/${channelId}/reauth`, 'POST');
        if (result.ok) {
            toast('✅ ' + (result.message || 'Conta trocada com sucesso!'), 'success');
            fetchChannels();
        } else {
            toast('❌ ' + (result.error || 'Erro ao trocar conta'), 'error');
        }
    } catch (e) {
        toast('❌ Erro: ' + (e?.message || e), 'error');
    }
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
    openTestPublishModal(channelId);
}

function openTestPublishModal(channelId) {
    const ch = channelsData.find(c => c.id === channelId);
    if (!ch) return;

    // Remove modal anterior se existir
    const old = document.getElementById('modal-test-publish');
    if (old) old.remove();

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'modal-test-publish';
    modal.innerHTML = `
        <div class="modal modal-lg">
            <div class="modal-header">
                <h3><i class="fas fa-flask"></i> Teste de Publicação — ${esc(ch.name)}</h3>
                <button class="modal-close" onclick="document.getElementById('modal-test-publish').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="test-publish-info">
                    <div class="test-channel-preview">
                        ${ch.channel_thumbnail
                            ? `<img src="${esc(ch.channel_thumbnail)}" class="test-channel-avatar" onerror="this.style.display='none'">`
                            : '<div class="test-channel-avatar-placeholder"><i class="fab fa-youtube"></i></div>'
                        }
                        <div>
                            <strong>${esc(ch.name)}</strong>
                            <div style="font-size:0.8rem;color:var(--text-muted)">${esc(ch.channel_url || '')}</div>
                        </div>
                    </div>
                </div>
                <div class="test-publish-logs" id="test-publish-logs">
                    <div class="log-line log-info">A aguardar início do teste...</div>
                </div>
                <div class="test-publish-result" id="test-publish-result" style="display:none"></div>
            </div>
            <div class="modal-footer">
                <button class="btn" onclick="document.getElementById('modal-test-publish').remove()">Fechar</button>
                <button class="btn btn-primary" id="test-publish-btn" onclick="runTestPublish('${channelId}')">
                    <i class="fas fa-play"></i> Iniciar Teste
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

async function runTestPublish(channelId) {
    const logsEl = document.getElementById('test-publish-logs');
    const resultEl = document.getElementById('test-publish-result');
    const btn = document.getElementById('test-publish-btn');
    if (!logsEl || !btn) return;

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> A testar...';
    logsEl.innerHTML = '<div class="log-line log-info"><i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> A iniciar teste completo...</div>';
    resultEl.style.display = 'none';

    try {
        const result = await api(`/api/channels/${channelId}/test-publish`, 'POST');
        const logs = result.logs || [];

        // Renderiza logs
        logsEl.innerHTML = logs.map(line => {
            if (!line.trim()) return '<div class="log-line log-empty">&nbsp;</div>';
            if (line.startsWith('===')) return `<div class="log-line log-header">${esc(line)}</div>`;
            if (line.startsWith('[')) return `<div class="log-line log-step">${esc(line)}</div>`;
            if (line.startsWith('OK')) return `<div class="log-line log-ok"><i class="fas fa-check"></i> ${esc(line.substring(5))}</div>`;
            if (line.startsWith('FALHOU')) return `<div class="log-line log-fail"><i class="fas fa-times"></i> ${esc(line.substring(9))}</div>`;
            if (line.startsWith('AVISO')) return `<div class="log-line log-warn"><i class="fas fa-exclamation-triangle"></i> ${esc(line.substring(8))}</div>`;
            if (line.startsWith('→')) return `<div class="log-line log-hint">${esc(line)}</div>`;
            return `<div class="log-line">${esc(line)}</div>`;
        }).join('');

        // Scroll to bottom
        logsEl.scrollTop = logsEl.scrollHeight;

        // Resultado final
        if (result.success) {
            resultEl.innerHTML = `<div class="test-result-ok"><i class="fas fa-check-circle"></i> Teste concluído com sucesso! Canal pronto para publicar.</div>`;
            // Atualizar dados do canal
            await fetchChannels();
        } else {
            resultEl.innerHTML = `<div class="test-result-fail"><i class="fas fa-times-circle"></i> Teste falhou. Verifica os logs acima.</div>`;
        }
        resultEl.style.display = 'block';
    } catch (err) {
        logsEl.innerHTML = `<div class="log-line log-fail"><i class="fas fa-times"></i> Erro de comunicação: ${esc(err.message || String(err))}</div>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-redo"></i> Repetir Teste';
    }
}

function openChannelSettingsModal(channelId) {
    const ch = channelsData.find(c => c.id === channelId);
    if (!ch) return;

    // Remove modal anterior se existir
    const old = document.getElementById('modal-channel-settings');
    if (old) old.remove();

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'modal-channel-settings';
    modal.innerHTML = `
        <div class="modal modal-lg">
            <div class="modal-header">
                <h3><i class="fas fa-cog"></i> Definições — ${esc(ch.name)}</h3>
                <button class="modal-close" onclick="document.getElementById('modal-channel-settings').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="channel-settings-preview">
                    ${ch.channel_thumbnail
                        ? `<img src="${esc(ch.channel_thumbnail)}" class="cs-avatar" onerror="this.nextElementSibling.style.display='flex';this.style.display='none'">`
                        : ''}
                    <div class="cs-avatar-placeholder" ${ch.channel_thumbnail ? 'style="display:none"' : ''}><i class="fab fa-youtube"></i></div>
                    <div class="cs-info">
                        <div class="cs-name">${esc(ch.name)}</div>
                        ${ch.youtube_channel_name ? `<div class="cs-yt-name">${esc(ch.youtube_channel_name)}</div>` : ''}
                        ${ch.youtube_subscribers ? `<div class="cs-subs"><i class="fas fa-users"></i> ${formatNumber(parseInt(ch.youtube_subscribers))} subscritores</div>` : ''}
                    </div>
                    <button class="btn btn-sm" onclick="refreshChannelInfo('${ch.id}')" id="cs-refresh-btn" title="Atualizar foto e info">
                        <i class="fas fa-sync-alt"></i>
                    </button>
                </div>

                <div class="cs-section">
                    <h4><i class="fas fa-info-circle"></i> Informações Gerais</h4>
                    <div class="form-group">
                        <label>Nome do Canal</label>
                        <input type="text" id="cs-name" class="form-control" value="${esc(ch.name)}">
                    </div>
                    <div class="form-group">
                        <label>URL do Canal YouTube</label>
                        <input type="url" id="cs-url" class="form-control" value="${esc(ch.channel_url || '')}" placeholder="https://www.youtube.com/@canal">
                    </div>
                    <div class="form-group">
                        <label>Descrição / Notas</label>
                        <textarea id="cs-description" class="form-control" rows="2" placeholder="Notas sobre este canal...">${esc(ch.description || '')}</textarea>
                    </div>
                </div>

                <div class="cs-section">
                    <h4><i class="fas fa-key"></i> Autenticação OAuth 2.0</h4>
                    <div class="form-group">
                        <label>Caminho do client_secrets.json</label>
                        <input type="text" id="cs-credentials" class="form-control" value="${esc(ch.credentials_path || '')}" placeholder="C:\\caminho\\para\\client_secrets.json">
                        <small style="color:var(--text-muted)">Ficheiro de credenciais OAuth descarregado do Google Cloud Console</small>
                    </div>
                    <div class="cs-oauth-status">
                        ${ch.credentials_path
                            ? `<span class="tag green"><i class="fas fa-check"></i> Credenciais configuradas</span>`
                            : `<span class="tag orange"><i class="fas fa-exclamation-triangle"></i> Sem credenciais</span>`
                        }
                        ${ch.youtube_channel_id
                            ? `<span class="tag green"><i class="fas fa-link"></i> Conta ligada</span>`
                            : `<span class="tag muted"><i class="fas fa-unlink"></i> Conta não ligada</span>`
                        }
                    </div>
                    <div class="info-box" style="margin-top:12px">
                        <i class="fas fa-info-circle"></i>
                        <div>
                            <strong>Como obter credenciais:</strong>
                            <ol style="margin:8px 0 0 16px;font-size:0.85rem">
                                <li>Vai a <a href="https://console.cloud.google.com" target="_blank">Google Cloud Console</a></li>
                                <li>Cria um projeto e ativa a <strong>YouTube Data API v3</strong></li>
                                <li>Vai a Credenciais → Criar credenciais → <strong>OAuth 2.0 (Desktop App)</strong></li>
                                <li>Faz download do <code>client_secrets.json</code></li>
                                <li>Cola o caminho completo do ficheiro acima</li>
                            </ol>
                        </div>
                    </div>
                </div>

                <div class="cs-section">
                    <h4><i class="fas fa-upload"></i> Definições de Publicação</h4>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Privacidade padrão</label>
                            <select id="cs-privacy" class="form-control">
                                <option value="private" ${(ch.default_privacy || 'private') === 'private' ? 'selected' : ''}>Privado</option>
                                <option value="unlisted" ${ch.default_privacy === 'unlisted' ? 'selected' : ''}>Não listado</option>
                                <option value="public" ${ch.default_privacy === 'public' ? 'selected' : ''}>Público</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Categoria do vídeo</label>
                            <select id="cs-category" class="form-control">
                                <option value="22" ${(ch.default_category || '22') === '22' ? 'selected' : ''}>Pessoas e Blogs</option>
                                <option value="24" ${ch.default_category === '24' ? 'selected' : ''}>Entretenimento</option>
                                <option value="20" ${ch.default_category === '20' ? 'selected' : ''}>Gaming</option>
                                <option value="23" ${ch.default_category === '23' ? 'selected' : ''}>Comédia</option>
                                <option value="17" ${ch.default_category === '17' ? 'selected' : ''}>Desporto</option>
                                <option value="25" ${ch.default_category === '25' ? 'selected' : ''}>Notícias</option>
                                <option value="26" ${ch.default_category === '26' ? 'selected' : ''}>How-to & Style</option>
                                <option value="28" ${ch.default_category === '28' ? 'selected' : ''}>Ciência & Tecnologia</option>
                                <option value="10" ${ch.default_category === '10' ? 'selected' : ''}>Música</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Tags padrão (separadas por vírgula)</label>
                        <input type="text" id="cs-tags" class="form-control" value="${esc(ch.default_tags || '')}" placeholder="clips, shorts, youtube">
                    </div>
                    <div class="form-group">
                        <label>Descrição padrão do vídeo</label>
                        <textarea id="cs-video-desc" class="form-control" rows="3" placeholder="Descrição padrão adicionada aos vídeos publicados...">${esc(ch.default_video_description || '')}</textarea>
                        <small style="color:var(--text-muted)">Usa {titulo} e {canal_fonte} como variáveis</small>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn" onclick="document.getElementById('modal-channel-settings').remove()">Cancelar</button>
                <button class="btn btn-primary" onclick="saveChannelSettings('${ch.id}')">
                    <i class="fas fa-save"></i> Guardar
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

async function saveChannelSettings(channelId) {
    const data = {
        name: document.getElementById('cs-name').value.trim(),
        channel_url: document.getElementById('cs-url').value.trim(),
        description: document.getElementById('cs-description').value.trim(),
        credentials_path: document.getElementById('cs-credentials').value.trim(),
        default_privacy: document.getElementById('cs-privacy').value,
        default_category: document.getElementById('cs-category').value,
        default_tags: document.getElementById('cs-tags').value.trim(),
        default_video_description: document.getElementById('cs-video-desc').value.trim(),
    };

    if (!data.name) {
        toast('Nome do canal é obrigatório', 'error');
        return;
    }

    await api(`/api/channels/${channelId}`, 'PATCH', data);
    document.getElementById('modal-channel-settings').remove();
    toast('Definições guardadas!', 'success');
    await fetchChannels();
}

async function refreshChannelInfo(channelId) {
    const btn = document.getElementById('cs-refresh-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i>';
    }
    try {
        await api(`/api/channels/${channelId}/refresh-info`, 'POST');
        toast('Informação do canal atualizada!', 'success');
        await fetchChannels();
        // Re-abrir modal com dados atualizados
        document.getElementById('modal-channel-settings')?.remove();
        openChannelSettingsModal(channelId);
    } catch (err) {
        toast('Erro ao atualizar informação', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sync-alt"></i>';
        }
    }
}

// ═══════════════ CHANNEL DETAIL MODAL (últimos vídeos) ═══════════════

function openChannelDetailModal(channelId) {
    const ch = channelsData.find(c => c.id === channelId);
    if (!ch) return;

    const old = document.getElementById('modal-channel-detail');
    if (old) old.remove();

    const hasThumb = ch.channel_thumbnail && ch.channel_thumbnail.length > 10;
    const ytName = ch.youtube_channel_name || '';
    const ytSubs = ch.youtube_subscribers || '';
    const ytVideos = ch.youtube_video_count || ch.videos_posted || 0;
    const ytViews = ch.youtube_view_count || ch.total_views || 0;

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'modal-channel-detail';
    modal.innerHTML = `
        <div class="modal modal-xl">
            <div class="modal-header">
                <h3><i class="fab fa-youtube"></i> ${esc(ch.name)}</h3>
                <button class="modal-close" onclick="document.getElementById('modal-channel-detail').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="cd-header">
                    ${hasThumb
                        ? `<img class="cd-avatar" src="${esc(ch.channel_thumbnail)}" alt="${esc(ch.name)}" onerror="this.nextElementSibling.style.display='flex';this.style.display='none'">`
                        : ''}
                    <div class="cd-avatar-placeholder" ${hasThumb ? 'style="display:none"' : ''}><i class="fab fa-youtube"></i></div>
                    <div class="cd-info">
                        <div class="cd-name">${esc(ch.name)}</div>
                        ${ytName && ytName !== ch.name ? `<div class="cd-yt-name">${esc(ytName)}</div>` : ''}
                        <div class="cd-url">${esc(ch.channel_url || '')}</div>
                    </div>
                    <div class="cd-stats-row">
                        <div class="cd-stat">
                            <div class="cd-stat-val">${formatNumber(parseInt(ytSubs) || 0)}</div>
                            <div class="cd-stat-lbl">Subscritores</div>
                        </div>
                        <div class="cd-stat">
                            <div class="cd-stat-val">${formatNumber(parseInt(ytVideos) || 0)}</div>
                            <div class="cd-stat-lbl">Vídeos</div>
                        </div>
                        <div class="cd-stat">
                            <div class="cd-stat-val">${formatNumber(parseInt(ytViews) || 0)}</div>
                            <div class="cd-stat-lbl">Views</div>
                        </div>
                    </div>
                </div>

                <div class="cd-section-header">
                    <h4><i class="fas fa-play-circle"></i> Últimos Vídeos</h4>
                    <button class="btn btn-sm" id="cd-refresh-btn" onclick="loadChannelVideos('${ch.id}')">
                        <i class="fas fa-sync-alt"></i> Atualizar
                    </button>
                </div>
                <div class="cd-videos-grid" id="cd-videos-grid">
                    <div class="cd-loading">
                        <i class="fas fa-spinner" style="animation:spin 1s linear infinite;font-size:1.5rem"></i>
                        <span>A carregar vídeos...</span>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn" onclick="document.getElementById('modal-channel-detail').remove()">Fechar</button>
                <button class="btn btn-sm" onclick="openChannelSettingsModal('${ch.id}');document.getElementById('modal-channel-detail').remove()">
                    <i class="fas fa-cog"></i> Definições
                </button>
                ${ch.channel_url ? `<a class="btn btn-primary" href="${esc(ch.channel_url)}" target="_blank">
                    <i class="fas fa-external-link-alt"></i> Ver no YouTube
                </a>` : ''}
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // Carregar vídeos automaticamente
    loadChannelVideos(channelId);
}

async function loadChannelVideos(channelId) {
    const grid = document.getElementById('cd-videos-grid');
    const btn = document.getElementById('cd-refresh-btn');
    if (!grid) return;

    grid.innerHTML = `
        <div class="cd-loading">
            <i class="fas fa-spinner" style="animation:spin 1s linear infinite;font-size:1.5rem"></i>
            <span>A carregar vídeos...</span>
        </div>`;
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> A carregar...';
    }

    try {
        const result = await api(`/api/channels/${channelId}/videos`);
        const videos = result.videos || [];

        if (videos.length === 0) {
            grid.innerHTML = `
                <div class="cd-empty">
                    <i class="fas fa-video-slash"></i>
                    <span>Nenhum vídeo encontrado</span>
                </div>`;
            return;
        }

        grid.innerHTML = videos.map(v => `
            <a class="cd-video-card" href="${esc(v.url)}" target="_blank" title="${esc(v.title)}">
                <div class="cd-video-thumb-wrap">
                    <img class="cd-video-thumb" src="${esc(v.thumbnail)}" alt="${esc(v.title)}" loading="lazy" onerror="this.src='https://i.ytimg.com/vi/${esc(v.id)}/hqdefault.jpg'">
                    ${v.duration ? `<span class="cd-video-duration">${esc(v.duration)}</span>` : ''}
                </div>
                <div class="cd-video-info">
                    <div class="cd-video-title">${esc(v.title)}</div>
                    <div class="cd-video-meta">
                        ${v.views != null ? `<span><i class="fas fa-eye"></i> ${formatNumber(v.views)}</span>` : ''}
                        ${v.date ? `<span><i class="fas fa-calendar"></i> ${esc(v.date)}</span>` : ''}
                    </div>
                </div>
            </a>
        `).join('');

        // Also refresh channel data in background
        await fetchChannels();
    } catch (err) {
        grid.innerHTML = `
            <div class="cd-empty">
                <i class="fas fa-exclamation-triangle"></i>
                <span>Erro ao carregar vídeos: ${esc(err.message || String(err))}</span>
            </div>`;
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sync-alt"></i> Atualizar';
        }
    }
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
                <div style="display: flex; gap: 8px; margin-top: 8px;">
                    <a href="${esc(v.video_url || '#')}" target="_blank" class="source-video-link">
                        <i class="fas fa-external-link-alt"></i> Ver no YouTube
                    </a>
                    <button class="btn-requeue" onclick="requeueVideo('${esc(v.video_url || '')}', '${esc(v.title || 'Vídeo')}', event)" title="Adicionar à Queue">
                        <i class="fas fa-plus"></i> Queue
                    </button>
                </div>
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

async function requeueVideo(videoUrl, videoTitle, event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    
    if (!videoUrl) {
        toast('URL do vídeo inválida', 'error');
        return;
    }

    try {
        await api('/api/queue', 'POST', {
            url: videoUrl,
            title: videoTitle
        });
        toast('Vídeo adicionado à queue', 'success');
        await fetchQueue();
        await fetchFollowedChannels();
        if (selectedFollowedId) {
            await fetchFollowedVideos(selectedFollowedId);
        }
    } catch (error) {
        toast('Erro ao adicionar vídeo à queue', 'error');
    }
}

function formatTime(minutes) {
    if (minutes < 60) return `${minutes}min`;
    if (minutes < 1440) {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return mins > 0 ? `${hours}h ${mins}min` : `${hours}h`;
    }
    const days = Math.floor(minutes / 1440);
    const hours = Math.floor((minutes % 1440) / 60);
    return hours > 0 ? `${days}d ${hours}h` : `${days}d`;
}

function openAutoScanModal() {
    const settings = settingsData || {};
    const currentInterval = settings.auto_scan_interval_minutes || 30;
    
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h3>Configurar Scan Automático</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Intervalo de Scan</label>
                    <div style="display:flex;gap:10px;align-items:center">
                        <input type="number" id="scan-interval-input" class="form-control" value="${currentInterval}" min="5" max="10080" step="5" onchange="updateScanIntervalDisplay()">
                        <span id="scan-interval-display" style="font-weight:500;min-width:60px">${formatTime(currentInterval)}</span>
                    </div>
                    <small style="color:var(--text-muted)">Entre 5 minutos e 7 dias</small>
                </div>
                <div style="margin-top:16px;padding:12px;background:var(--bg-hover);border-radius:var(--radius);font-size:0.9rem;color:var(--text-secondary)">
                    <i class="fas fa-info-circle"></i> O scan automático verifica novos vídeos dos canais que segues e adiciona à queue automaticamente.
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
                <button class="btn btn-primary" onclick="saveAutoScanInterval(document.getElementById('scan-interval-input').value); this.closest('.modal-overlay').remove()">Guardar</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    document.getElementById('scan-interval-input').focus();
}

function updateScanIntervalDisplay() {
    const input = document.getElementById('scan-interval-input');
    const display = document.getElementById('scan-interval-display');
    if (input && display) {
        const minutes = parseInt(input.value);
        if (!isNaN(minutes)) {
            display.textContent = formatTime(minutes);
        }
    }
}

async function saveAutoScanInterval(minutes) {
    const min = parseInt(minutes);
    if (isNaN(min) || min < 5 || min > 10080) {
        toast('Intervalo deve estar entre 5 minutos e 7 dias', 'error');
        return;
    }
    
    await api('/api/settings', 'PATCH', { auto_scan_interval_minutes: min });
    settingsData.auto_scan_interval_minutes = min;
    toast(`Scan automático configurado para ${formatTime(min)}`, 'success');
    
    // Reinicia o countdown com o novo intervalo
    initScanCountdown();
}

async function instantScan(btn) {
    if (!btn) return;
    
    btn.disabled = true;
    const originalHTML = btn.innerHTML;
    
    try {
        // Busca canais ativos para mostrar progresso
        const channels = (followedChannelsData || []).filter(c => c.active !== false);
        const total = channels.length;
        
        if (total === 0) {
            toast('Nenhum canal a seguir ativo', 'info');
            return;
        }
        
        let enqueuedTotal = 0;
        
        // Scan canal a canal com progresso
        for (let i = 0; i < channels.length; i++) {
            const ch = channels[i];
            const name = ch.name || `Canal ${i + 1}`;
            btn.innerHTML = `<i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> ${i + 1}/${total} — ${name}`;
            
            try {
                const result = await api(`/api/followed-channels/${ch.id}/scan`, 'POST');
                if (result && result.enqueued) {
                    enqueuedTotal += result.enqueued;
                }
            } catch (err) {
                console.error(`Erro ao fazer scan de ${name}:`, err);
            }
        }
        
        // Atualiza as listas
        btn.innerHTML = '<i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> A atualizar...';
        await fetchQueue();
        await fetchFollowedChannels();
        if (selectedFollowedId) {
            await fetchFollowedVideos(selectedFollowedId);
        }
        
        if (enqueuedTotal > 0) {
            toast(`${enqueuedTotal} vídeo(s) adicionado(s) à queue!`, 'success');
        } else {
            toast('Nenhum vídeo novo encontrado', 'info');
        }
    } catch (error) {
        console.error('Erro ao fazer scan:', error);
        toast('Erro ao fazer scan', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
        // Reinicia o countdown após scan instantâneo
        initScanCountdown();
    }
}

function initScanCountdown() {
    // Limpa intervalo anterior se existir
    if (scanCountdownInterval) {
        clearInterval(scanCountdownInterval);
    }
    
    // Calcula o tempo do próximo scan (agora + intervalo)
    const interval = (settingsData.auto_scan_interval_minutes || 30) * 60 * 1000; // convert to ms
    nextScanTime = Date.now() + interval;
    
    // Atualiza imediatamente
    updateScanCountdown();
    
    // Atualiza a cada segundo
    scanCountdownInterval = setInterval(updateScanCountdown, 1000);
}

function updateScanCountdown() {
    const countdownEl = document.getElementById('next-scan-countdown');
    if (!countdownEl) return;
    
    if (!nextScanTime) {
        countdownEl.textContent = '—';
        return;
    }
    
    const now = Date.now();
    const diff = nextScanTime - now;
    
    if (diff <= 0) {
        countdownEl.textContent = 'a fazer scan...';
        // Limpa o intervalo para não disparar várias vezes
        if (scanCountdownInterval) {
            clearInterval(scanCountdownInterval);
            scanCountdownInterval = null;
        }
        // Executa o scan e reinicia o countdown
        scanAllFollowedChannels().then(() => {
            initScanCountdown();
        }).catch(() => {
            initScanCountdown();
        });
        return;
    }
    
    const totalSeconds = Math.floor(diff / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    
    if (days > 0) {
        countdownEl.textContent = `${days}d ${hours}h`;
    } else if (hours > 0) {
        countdownEl.textContent = `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
        countdownEl.textContent = `${minutes}m ${seconds}s`;
    } else {
        countdownEl.textContent = `${seconds}s`;
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

function _parseDuration(iso) {
    // PT1M30S → 1:30, PT1H2M3S → 1:02:03
    if (!iso) return '';
    const m = iso.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
    if (!m) return '';
    const h = parseInt(m[1] || 0), min = parseInt(m[2] || 0), s = parseInt(m[3] || 0);
    if (h) return `${h}:${String(min).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${min}:${String(s).padStart(2, '0')}`;
}

function _privacyLabel(p) {
    const map = {
        'public': { icon: 'fas fa-globe', text: 'Público', cls: 'privacy-public' },
        'unlisted': { icon: 'fas fa-eye-slash', text: 'Não listado', cls: 'privacy-unlisted' },
        'private': { icon: 'fas fa-lock', text: 'Privado', cls: 'privacy-private' },
    };
    return map[p] || { icon: 'fas fa-question', text: p || '?', cls: 'privacy-unknown' };
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

    // Header with sync button
    const hasYtVideos = postedData.some(v => v.youtube_video_id);

    grid.innerHTML = `
        <div class="posted-header">
            <div class="posted-header-left">
                <span class="posted-count">${postedData.length} vídeo${postedData.length !== 1 ? 's' : ''}</span>
            </div>
            <div class="posted-header-right">
                ${hasYtVideos ? `<button class="btn btn-sm" id="sync-posted-btn" onclick="syncPostedVideos()">
                    <i class="fas fa-sync-alt"></i> Sincronizar com YouTube
                </button>` : ''}
            </div>
        </div>
        <div class="posted-table-wrap">
            <table class="posted-table">
                <thead>
                    <tr>
                        <th class="posted-th-video">Vídeo</th>
                        <th class="posted-th-vis">Visibilidade</th>
                        <th class="posted-th-date">Data</th>
                        <th class="posted-th-views">Views</th>
                        <th class="posted-th-likes">Likes</th>
                        <th class="posted-th-comments">Comentários</th>
                        <th class="posted-th-actions"></th>
                    </tr>
                </thead>
                <tbody>
                    ${postedData.map(v => {
                        const channelName = getChannelName(v.channel_id);
                        const ytUrl = v.youtube_url || '';
                        const thumb = v.youtube_thumbnail || v.thumbnail || '';
                        const ytTitle = v.youtube_title || v.title || 'Clip';
                        const privacy = _privacyLabel(v.youtube_privacy || '');
                        const duration = _parseDuration(v.youtube_duration);
                        const definition = v.youtube_definition === 'hd' ? 'HD' : (v.youtube_definition === 'sd' ? 'SD' : '');
                        const uploadStatus = v.youtube_upload_status || '';

                        // Date  
                        let dateStr = '';
                        if (v.youtube_published_at) {
                            dateStr = new Date(v.youtube_published_at).toLocaleDateString('pt-PT', { day: '2-digit', month: 'short', year: 'numeric' });
                        } else if (v.published_at) {
                            dateStr = new Date(v.published_at).toLocaleDateString('pt-PT', { day: '2-digit', month: 'short', year: 'numeric' });
                        }

                        const hasYt = !!v.youtube_video_id;

                        return `<tr class="posted-row ${!hasYt ? 'posted-row-local' : ''}">
                            <td class="posted-td-video">
                                <div class="posted-video-cell">
                                    <div class="posted-thumb-wrap">
                                        ${thumb
                                            ? `<img class="posted-thumb" src="${esc(thumb)}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
                                               <div class="posted-thumb-placeholder" style="display:none"><i class="fas fa-film"></i></div>`
                                            : `<div class="posted-thumb-placeholder"><i class="fas fa-film"></i></div>`
                                        }
                                        ${duration ? `<span class="posted-duration">${esc(duration)}</span>` : ''}
                                        ${definition ? `<span class="posted-definition">${definition}</span>` : ''}
                                    </div>
                                    <div class="posted-video-info">
                                        <div class="posted-video-title">${ytUrl ? `<a href="${esc(ytUrl)}" target="_blank">${esc(ytTitle)}</a>` : esc(ytTitle)}</div>
                                        <div class="posted-video-meta">
                                            ${channelName ? `<span><i class="fab fa-youtube" style="color:#ff0000"></i> ${esc(channelName)}</span>` : ''}
                                            ${v.youtube_video_id ? `<span class="posted-yt-id">${esc(v.youtube_video_id)}</span>` : '<span class="tag muted" style="font-size:0.65rem">Local</span>'}
                                        </div>
                                        ${v.description ? `<div class="posted-video-desc">${esc((v.description || '').substring(0, 80))}${(v.description||'').length > 80 ? '...' : ''}</div>` : ''}
                                    </div>
                                </div>
                            </td>
                            <td class="posted-td-vis">
                                ${hasYt ? `<span class="privacy-badge ${privacy.cls}"><i class="${privacy.icon}"></i> ${privacy.text}</span>` : '<span class="privacy-badge privacy-unknown"><i class="fas fa-desktop"></i> Local</span>'}
                                ${uploadStatus === 'processing' ? '<div class="upload-processing"><i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> A processar</div>' : ''}
                            </td>
                            <td class="posted-td-date">${dateStr}</td>
                            <td class="posted-td-stat">${hasYt ? formatNumber(v.youtube_views || v.views || 0) : '—'}</td>
                            <td class="posted-td-stat">${hasYt ? formatNumber(v.youtube_likes || v.likes || 0) : '—'}</td>
                            <td class="posted-td-stat">${hasYt ? formatNumber(v.youtube_comments || v.comments || 0) : '—'}</td>
                            <td class="posted-td-actions">
                                <div class="posted-row-actions">
                                    ${ytUrl ? `<a href="${esc(ytUrl)}" target="_blank" class="btn btn-sm btn-icon" title="Ver no YouTube"><i class="fab fa-youtube"></i></a>` : ''}
                                    ${hasYt ? `<a href="https://studio.youtube.com/video/${esc(v.youtube_video_id)}/edit" target="_blank" class="btn btn-sm btn-icon" title="YouTube Studio"><i class="fas fa-edit"></i></a>` : ''}
                                    <button class="btn btn-sm btn-icon btn-danger" onclick="deletePostedVideo('${v.id}')" title="Apagar"><i class="fas fa-trash"></i></button>
                                </div>
                            </td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
        </div>`;
}

async function syncPostedVideos() {
    const btn = document.getElementById('sync-posted-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner" style="animation:spin 1s linear infinite"></i> A sincronizar...';
    }
    try {
        const result = await api('/api/posted/sync', 'POST');
        if (result.synced > 0) {
            toast(`${result.synced} vídeo(s) sincronizado(s) com YouTube`, 'success');
        } else {
            toast('Nenhum vídeo para sincronizar', 'info');
        }
        await fetchPosted();
    } catch (err) {
        toast('Erro ao sincronizar com YouTube', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sync-alt"></i> Sincronizar com YouTube';
        }
    }
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
    // Inicia o countdown do scan automático quando as definições são carregadas
    if (!scanCountdownInterval && currentPage === 'followed') {
        initScanCountdown();
    }
}

function renderSettings() {
    if (!settingsData) return;
    document.getElementById('setting-ollama-model').value = settingsData.ollama_model || 'llama2';
    document.getElementById('setting-max-clips').value = settingsData.max_clips_per_video || 7;
    document.getElementById('setting-clip-min').value = settingsData.clip_duration_min || 30;
    document.getElementById('setting-clip-max').value = settingsData.clip_duration_max || 60;
    document.getElementById('setting-max-video-duration').value = settingsData.max_video_duration_min || 60;
    document.getElementById('setting-auto-publish').checked = settingsData.auto_publish || false;
    document.getElementById('setting-usar-video-satisfatorio').checked = settingsData.usar_video_satisfatorio !== false;

    // Scheduled publishing settings
    document.getElementById('setting-schedule-enabled').checked = settingsData.schedule_enabled !== false; // default true
    document.getElementById('setting-schedule-interval').value = settingsData.schedule_interval_hours || 2;
    document.getElementById('setting-schedule-max-batch').value = settingsData.schedule_max_per_batch || 5;

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
        usar_video_satisfatorio: document.getElementById('setting-usar-video-satisfatorio').checked,
        default_channel_id: document.getElementById('setting-default-channel').value || null,
        schedule_enabled: document.getElementById('setting-schedule-enabled').checked,
        schedule_interval_hours: parseFloat(document.getElementById('setting-schedule-interval').value) || 2,
        schedule_max_per_batch: parseInt(document.getElementById('setting-schedule-max-batch').value) || 5,
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
}

// ═══════════════════════════════════════════════
//  ADD VIDEO MODAL - FILE UPLOAD
// ═══════════════════════════════════════════════

function setupAddVideoModal() {
    const dropArea = document.getElementById('file-drop-area');
    const fileInput = document.getElementById('video-file');
    const originUrlInput = document.getElementById('video-origin-url');

    // Click to open file dialog
    dropArea.addEventListener('click', () => fileInput.click());

    // Drag and drop
    dropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropArea.style.backgroundColor = 'rgba(100, 200, 255, 0.1)';
        dropArea.style.borderColor = 'var(--primary)';
    });

    dropArea.addEventListener('dragleave', () => {
        dropArea.style.backgroundColor = '';
        dropArea.style.borderColor = '';
    });

    dropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dropArea.style.backgroundColor = '';
        dropArea.style.borderColor = '';
        
        const files = e.dataTransfer.files;
        if (files && files[0] && files[0].type.startsWith('video/')) {
            fileInput.files = files;
            updateFileDisplay();
        } else {
            toast('Por favor, solte um ficheiro de vídeo', 'error');
        }
    });

    // File selection
    fileInput.addEventListener('change', updateFileDisplay);

    // Get video info from origin URL
    originUrlInput.addEventListener('blur', () => fetchVideoOriginInfo());
    originUrlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') fetchVideoOriginInfo();
    });
}

function updateFileDisplay() {
    const fileInput = document.getElementById('video-file');
    const display = document.getElementById('file-name-display');
    const text = document.getElementById('file-name-text');

    if (fileInput.files && fileInput.files[0]) {
        const file = fileInput.files[0];
        const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
        text.textContent = `${file.name} (${sizeMB}MB)`;
        display.style.display = 'block';
    } else {
        display.style.display = 'none';
    }
}

async function fetchVideoOriginInfo() {
    const urlInput = document.getElementById('video-origin-url');
    const url = urlInput.value.trim();
    const statusEl = document.getElementById('video-origin-status');
    const infoEl = document.getElementById('video-origin-info');
    const titleDisplay = document.getElementById('origin-title-display');
    const channelDisplay = document.getElementById('origin-channel-display');

    if (!url) {
        infoEl.style.display = 'none';
        statusEl.textContent = 'Cole a URL original para auto-preencher nome, canal e descrição';
        return;
    }

    statusEl.textContent = '🔍 A carregar informações...';
    
    try {
        const result = await api('/api/video/fetch-info', 'POST', { url });
        
        if (result.error) {
            statusEl.textContent = `❌ ${result.error}`;
            infoEl.style.display = 'none';
            return;
        }

        // Store origin data globally (will be used when uploading)
        window.videoOriginData = {
            title: result.title,
            url: result.url,
            channel_name: result.channel_name,
            channel_url: result.channel_url,
        };

        // Display extracted info
        titleDisplay.textContent = `📹 ${result.title}`;
        channelDisplay.textContent = `🎥 ${result.channel_name}`;
        
        // Auto-fill title if empty
        const titleInput = document.getElementById('video-file-title');
        if (!titleInput.value && result.title) {
            titleInput.value = result.title;
        }

        infoEl.style.display = 'block';
        statusEl.textContent = '✅ Informações carregadas';

    } catch (error) {
        statusEl.textContent = `❌ Erro ao carregar: ${error.message}`;
        infoEl.style.display = 'none';
    }
}

function switchAddVideoTab(tab) {
    const youtubeContent = document.getElementById('tab-youtube-content');
    const fileContent = document.getElementById('tab-file-content');
    const youtubeBtn = document.getElementById('tab-youtube-btn');
    const fileBtn = document.getElementById('tab-file-btn');

    if (tab === 'youtube') {
        youtubeContent.style.display = 'block';
        fileContent.style.display = 'none';
        youtubeBtn.style.borderBottomColor = 'var(--primary)';
        youtubeBtn.style.color = 'var(--primary)';
        fileBtn.style.borderBottomColor = 'transparent';
        fileBtn.style.color = 'inherit';
    } else {
        youtubeContent.style.display = 'none';
        fileContent.style.display = 'block';
        youtubeBtn.style.borderBottomColor = 'transparent';
        youtubeBtn.style.color = 'inherit';
        fileBtn.style.borderBottomColor = 'var(--primary)';
        fileBtn.style.color = 'var(--primary)';
    }
}

// ═══════════════════════════════════════════════
//  SCHEDULES (Rever Agendamentos)
// ═══════════════════════════════════════════════

async function fetchSchedules() {
    schedulesData = await api('/api/schedules');
    renderSchedules();
    updateSchedulesBadge();
    renderScheduleConfig();
}

async function syncSchedulesFromYouTube(btn) {
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> A sincronizar...'; }
    const infoEl = document.getElementById('schedules-sync-info');
    try {
        // 1. Sync posted videos data from YouTube (pulls real status)
        const syncResult = await api('/api/posted/sync', 'POST');
        // 2. Push local schedule changes to YouTube
        const pushResult = await api('/api/schedules/sync-youtube', 'POST');
        // 3. Refresh schedule data
        schedulesData = await api('/api/schedules');
        renderSchedules();
        updateSchedulesBadge();
        
        let msg = '<i class="fas fa-check-circle" style="color:var(--green)"></i> ';
        const parts = [];
        if (syncResult.synced !== undefined) parts.push(`${syncResult.synced} vídeos atualizados do YouTube`);
        if (pushResult.youtube_updated !== undefined && pushResult.youtube_updated > 0) parts.push(`${pushResult.youtube_updated} agendamentos enviados para YouTube`);
        if (pushResult.youtube_errors && pushResult.youtube_errors.length > 0) {
            parts.push(`<span style="color:var(--red)">${pushResult.youtube_errors.length} erros</span>`);
        }
        msg += parts.length ? parts.join(' · ') : 'Sincronização concluída';
        if (infoEl) { infoEl.innerHTML = msg; infoEl.style.display = 'block'; }
        toast('Sincronizado com YouTube!', 'success');
    } catch (e) {
        if (infoEl) { infoEl.innerHTML = `<i class="fas fa-exclamation-circle" style="color:var(--red)"></i> Erro: ${e.message || e}`; infoEl.style.display = 'block'; }
        toast('Erro ao sincronizar com YouTube', 'error');
    }
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fab fa-youtube"></i> Sincronizar com YouTube'; }
}

function updateSchedulesBadge() {
    const badge = document.getElementById('schedules-badge');
    if (!badge) return;
    const now = new Date();
    let count = 0;
    
    // Count future scheduled videos
    if (schedulesData.scheduled_videos) {
        count += schedulesData.scheduled_videos.filter(v => {
            const pubAt = v.youtube_publish_at;
            if (!pubAt) return false;
            const pubTime = new Date(pubAt);
            const ytPrivacy = v.youtube_privacy || '';
            // Count scheduled (future) + missed (past but still private)
            if (pubTime > now) return true;
            if (ytPrivacy === 'private' && pubTime <= now) return true;
            return false;
        }).length;
    }
    
    // Count future slots
    if (schedulesData.scheduled_slots) {
        for (const ch of Object.values(schedulesData.scheduled_slots)) {
            for (const ts of ch) {
                if (new Date(ts) > now) count++;
            }
        }
    }
    
    badge.textContent = count || '';
}

function renderScheduleConfig() {
    if (!schedulesData) return;
    
    const intervalEl = document.getElementById('sched-interval-hours');
    const perDayEl = document.getElementById('sched-videos-per-day');
    const startEl = document.getElementById('sched-start-time');
    const endEl = document.getElementById('sched-end-time');
    
    if (intervalEl) intervalEl.value = schedulesData.schedule_interval_hours || 2;
    if (perDayEl) perDayEl.value = schedulesData.schedule_videos_per_day || 12;
    if (startEl) startEl.value = schedulesData.schedule_start_time || '08:00';
    if (endEl) endEl.value = schedulesData.schedule_end_time || '22:00';
    
    // Populate channel filter
    const sel = document.getElementById('sched-filter-channel');
    if (sel && channelsData) {
        const currentVal = sel.value;
        sel.innerHTML = '<option value="">— Todos os canais —</option>';
        channelsData.forEach(ch => {
            sel.innerHTML += `<option value="${esc(ch.id)}">${esc(ch.name)}</option>`;
        });
        sel.value = currentVal;
    }
}

function renderSchedules() {
    const tbody = document.getElementById('schedules-tbody');
    const empty = document.getElementById('schedules-empty');
    const timeline = document.getElementById('schedules-timeline');
    
    if (!schedulesData) return;
    
    const now = new Date();
    
    // Combine scheduled videos and future slots into one list
    let allItems = [];
    
    // Add posted videos with publish_at
    if (schedulesData.scheduled_videos) {
        for (const v of schedulesData.scheduled_videos) {
            const pubAt = v.youtube_publish_at;
            if (!pubAt) continue;
            
            // Determine status from actual YouTube data when available
            const pubTime = new Date(pubAt);
            const ytPrivacy = v.youtube_privacy || '';
            let videoStatus;
            if (ytPrivacy === 'public') {
                videoStatus = 'published';
            } else if (pubTime > now) {
                videoStatus = 'scheduled';
            } else if (ytPrivacy === 'private' && pubTime <= now) {
                // Past the publish time but still private — might have failed to publish
                videoStatus = 'missed';
            } else {
                videoStatus = 'published';
            }
            
            allItems.push({
                type: 'video',
                time: pubTime,
                title: v.youtube_title || v.title || 'Clip',
                channel_id: v.channel_id,
                youtube_url: v.youtube_url || '',
                video_id: v.id,
                youtube_video_id: v.youtube_video_id || '',
                privacy: ytPrivacy || 'private',
                status: videoStatus,
            });
        }
    }
    
    // Add reserved slots
    if (schedulesData.scheduled_slots) {
        for (const [chId, slots] of Object.entries(schedulesData.scheduled_slots)) {
            for (const ts of slots) {
                const dt = new Date(ts);
                // Skip slots that already have a matching video
                // Use wider tolerance (5 min) to handle timezone offset inconsistencies
                const hasVideo = allItems.some(item => 
                    item.type === 'video' && 
                    item.channel_id === chId &&
                    Math.abs(item.time.getTime() - dt.getTime()) < 300000
                );
                if (!hasVideo) {
                    allItems.push({
                        type: 'slot',
                        time: dt,
                        title: 'Slot reservado',
                        channel_id: chId,
                        youtube_url: '',
                        video_id: null,
                        youtube_video_id: '',
                        privacy: 'private',
                        status: dt > now ? 'scheduled' : 'past',
                    });
                }
            }
        }
    }
    
    // Sort by time
    allItems.sort((a, b) => a.time - b.time);
    
    // Filter by channel if selected
    const filterChannel = document.getElementById('sched-filter-channel')?.value;
    if (filterChannel) {
        allItems = allItems.filter(item => item.channel_id === filterChannel);
    }
    
    if (allItems.length === 0) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        timeline.innerHTML = '';
        return;
    }
    
    empty.style.display = 'none';
    
    // Build timeline (group by day)
    const byDay = {};
    for (const item of allItems) {
        const dayKey = item.time.toLocaleDateString('pt-PT', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });
        if (!byDay[dayKey]) byDay[dayKey] = [];
        byDay[dayKey].push(item);
    }
    
    let timelineHtml = '';
    for (const [day, items] of Object.entries(byDay)) {
        const futureCount = items.filter(i => i.time > now).length;
        timelineHtml += `<div class="sched-timeline-day">
            <div class="sched-day-header">
                <i class="fas fa-calendar-day"></i> ${esc(day)}
                <span class="day-count">${items.length} vídeo${items.length !== 1 ? 's' : ''}${futureCount > 0 ? ` (${futureCount} pendente${futureCount !== 1 ? 's' : ''})` : ''}</span>
            </div>
            <div class="sched-day-slots">
                ${items.map(item => {
                    const isFuture = item.time > now;
                    const timeStr = item.time.toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' });
                    const icon = item.type === 'video' ? 'fas fa-video' : 'fas fa-clock';
                    return `<span class="sched-slot ${isFuture ? 'future' : 'past'}" title="${esc(item.title)}">
                        <i class="${icon}"></i> ${timeStr}
                    </span>`;
                }).join('')}
            </div>
        </div>`;
    }
    timeline.innerHTML = timelineHtml;
    
    // Build table
    tbody.innerHTML = allItems.map((item, idx) => {
        const isFuture = item.time > now;
        const channelName = getChannelName(item.channel_id);
        const timeStr = item.time.toLocaleString('pt-PT', { 
            day: '2-digit', month: 'short', year: 'numeric', 
            hour: '2-digit', minute: '2-digit' 
        });
        
        const statusBadge = item.status === 'scheduled' 
            ? '<span class="sched-status-badge scheduled"><i class="fas fa-clock"></i> Agendado</span>'
            : item.status === 'published'
            ? '<span class="sched-status-badge published"><i class="fas fa-check"></i> Publicado</span>'
            : item.status === 'missed'
            ? '<span class="sched-status-badge" style="background:var(--red);color:#fff"><i class="fas fa-exclamation-triangle"></i> Não publicou</span>'
            : '<span class="sched-status-badge past"><i class="fas fa-history"></i> Passado</span>';
        
        const privacyIcon = item.privacy === 'public' ? '<i class="fas fa-globe" title="Público" style="color:var(--green);margin-left:6px"></i>'
            : item.privacy === 'unlisted' ? '<i class="fas fa-eye-slash" title="Não listado" style="color:var(--orange);margin-left:6px"></i>'
            : item.privacy === 'private' ? '<i class="fas fa-lock" title="Privado" style="color:var(--text-muted);margin-left:6px"></i>' : '';
        
        const titleHtml = item.youtube_url 
            ? `<a href="${esc(item.youtube_url)}" target="_blank">${esc(item.title)}</a>`
            : esc(item.title);
        
        const typeIcon = item.type === 'video' 
            ? '<i class="fas fa-video" style="color:var(--accent)" title="Vídeo publicado"></i>'
            : '<i class="fas fa-clock" style="color:var(--text-muted)" title="Slot reservado"></i>';
        
        return `<tr>
            <td>${idx + 1}</td>
            <td><div class="sched-video-title">${typeIcon} ${titleHtml}${privacyIcon}</div></td>
            <td>${esc(channelName)}</td>
            <td><span class="${isFuture ? 'sched-time' : 'sched-time-past'}">${timeStr}</span></td>
            <td>${statusBadge}</td>
            <td class="sched-actions">
                ${item.youtube_url ? `<a href="${esc(item.youtube_url)}" target="_blank" class="btn btn-icon btn-sm" title="Ver no YouTube"><i class="fab fa-youtube" style="color:var(--red)"></i></a>` : ''}
                ${item.video_id ? `<button class="btn btn-icon btn-sm" onclick="removeScheduledVideo('${esc(item.video_id)}')" title="Remover">
                    <i class="fas fa-trash"></i>
                </button>` : ''}
            </td>
        </tr>`;
    }).join('');
}

async function saveScheduleConfig() {
    const data = {
        schedule_interval_hours: parseFloat(document.getElementById('sched-interval-hours').value) || 2,
        schedule_videos_per_day: parseInt(document.getElementById('sched-videos-per-day').value) || 12,
        schedule_start_time: document.getElementById('sched-start-time').value || '08:00',
        schedule_end_time: document.getElementById('sched-end-time').value || '22:00',
    };
    await api('/api/schedules/config', 'PATCH', data);
    toast('Configuração de agendamento guardada!', 'success');
    fetchSchedules();
}

async function rearrangeSchedules() {
    const channelId = document.getElementById('sched-filter-channel')?.value || null;
    const data = {
        channel_id: channelId,
        interval_hours: parseFloat(document.getElementById('sched-interval-hours').value) || 2,
        videos_per_day: parseInt(document.getElementById('sched-videos-per-day').value) || 12,
        start_time: document.getElementById('sched-start-time').value || '08:00',
        end_time: document.getElementById('sched-end-time').value || '22:00',
    };
    
    schedulesData = await api('/api/schedules/rearrange', 'POST', data);
    renderSchedules();
    updateSchedulesBadge();
    
    // Show YouTube sync feedback
    const infoEl = document.getElementById('schedules-sync-info');
    const ytUpdated = schedulesData.youtube_updated || 0;
    const ytErrors = schedulesData.youtube_errors || [];
    if (ytUpdated > 0 || ytErrors.length > 0) {
        let msg = '<i class="fas fa-info-circle" style="color:var(--blue)"></i> ';
        if (ytUpdated > 0) msg += `${ytUpdated} vídeos reagendados no YouTube`;
        if (ytErrors.length > 0) msg += ` · <span style="color:var(--red)">${ytErrors.length} erros: ${esc(ytErrors[0])}</span>`;
        if (infoEl) { infoEl.innerHTML = msg; infoEl.style.display = 'block'; }
    }
    toast('Agendamentos reorganizados!', 'success');
}

async function clearAllSchedules() {
    if (!confirm('Tens a certeza que queres limpar todos os agendamentos futuros?')) return;
    
    const channelId = document.getElementById('sched-filter-channel')?.value || null;
    await api('/api/schedules/clear', 'POST', { channel_id: channelId });
    toast('Agendamentos limpos!', 'success');
    fetchSchedules();
}

async function removeScheduledVideo(videoId) {
    if (!confirm('Remover este vídeo dos agendados?')) return;
    await api(`/api/posted/${videoId}`, 'PATCH', { youtube_publish_at: '' });
    toast('Agendamento removido', 'success');
    fetchSchedules();
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
