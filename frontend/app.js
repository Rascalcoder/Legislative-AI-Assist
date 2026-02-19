// Competition Law AI Assistant - Frontend
// Supports: Slovak, Hungarian, English
// Jurisdictions: SK (Slov-Lex, PMU) + EU (EUR-Lex, Commission, CJEU)

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || window.__API_BASE_URL__ || 'http://localhost:8000/api/v1';

// State
let currentConversationId = null;

// DOM Elements
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const jurisdictionFilter = document.getElementById('jurisdictionFilter');
const searchResults = document.getElementById('searchResults');
const uploadBtn = document.getElementById('uploadBtn');
const fileInput = document.getElementById('fileInput');
const documentsList = document.getElementById('documentsList');
const navItems = document.querySelectorAll('.nav-item');

// Judge Assistant DOM Elements
const judgeInput = document.getElementById('judgeInput');
const judgeLanguage = document.getElementById('judgeLanguage');
const judgeSubmitBtn = document.getElementById('judgeSubmitBtn');
const judgeNewBtn = document.getElementById('judgeNewBtn');
const judgeProgress = document.getElementById('judgeProgress');
const judgeInputPanel = document.getElementById('judgeInputPanel');
const judgeResultPanel = document.getElementById('judgeResultPanel');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadDocuments();
});

// Event Listeners
function initializeEventListeners() {
    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    newChatBtn.addEventListener('click', startNewChat);

    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileUpload);

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            switchView(e.currentTarget.dataset.view);
        });
    });

    // Auto-resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = chatInput.scrollHeight + 'px';
    });

    // Judge Assistant
    judgeSubmitBtn.addEventListener('click', runJudgeAnalysis);
    judgeNewBtn.addEventListener('click', resetJudgeView);
    judgeInput.addEventListener('keydown', (e) => {
        // Ctrl+Enter / Cmd+Enter submits
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            runJudgeAnalysis();
        }
    });
}

// View Switching
function switchView(viewName) {
    document.querySelectorAll('.view').forEach(view => view.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));

    document.getElementById(viewName + 'View').classList.add('active');
    document.querySelector(`[data-view="${viewName}"]`).classList.add('active');
}

// --- Jurisdiction badge helper ---
function jurisdictionBadge(jurisdiction, label) {
    if (!jurisdiction) return '';
    if (jurisdiction === 'EU') {
        return `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300">${label || '[EU]'}</span>`;
    }
    if (jurisdiction === 'SK') {
        return `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">${label || '[SK]'}</span>`;
    }
    return `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-gray-100 text-gray-600">${label || jurisdiction}</span>`;
}

// --- Verified badge helper ---
function verifiedBadge(verified) {
    if (!verified) return '';
    return `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700 border border-green-300">
        <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/></svg>
        Verified
    </span>`;
}

// Chat Functions
async function sendMessage() {
    const message = chatInput.value.trim();
    if (!message) return;

    addMessage('user', message);
    chatInput.value = '';
    chatInput.style.height = 'auto';

    sendBtn.disabled = true;
    chatInput.disabled = true;

    // Show typing indicator
    const typingId = showTypingIndicator();

    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                conversation_id: currentConversationId,
            })
        });

        if (!response.ok) throw new Error('Failed to get response');

        const data = await response.json();
        currentConversationId = data.conversation_id;

        removeTypingIndicator(typingId);
        addMessage('assistant', data.response, data.sources, data.confidence, data.language, data.verified);

    } catch (error) {
        console.error('Error:', error);
        removeTypingIndicator(typingId);
        showToast('Error sending message. Please try again.', 'error');
        addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
    } finally {
        sendBtn.disabled = false;
        chatInput.disabled = false;
        chatInput.focus();
    }
}

function showTypingIndicator() {
    const id = 'typing-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = 'message assistant msg-animate flex gap-4 mb-6';
    div.innerHTML = `
        <div class="w-9 h-9 rounded-full bg-emerald-500 text-white flex items-center justify-center flex-shrink-0 text-sm font-semibold">AI</div>
        <div class="flex-1 max-w-3xl">
            <div class="bg-white px-5 py-4 rounded-xl shadow-sm">
                <div class="flex gap-1.5">
                    <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay:0ms"></span>
                    <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay:150ms"></span>
                    <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay:300ms"></span>
                </div>
            </div>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function addMessage(role, content, sources = null, confidence = null, language = null, verified = false) {
    const welcomeMsg = chatMessages.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.remove();

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role} msg-animate flex gap-4 mb-6`;

    const isUser = role === 'user';
    const avatarColor = isUser ? 'bg-brand-500' : 'bg-emerald-500';
    const avatarText = isUser ? 'U' : 'AI';
    const bubbleClass = isUser
        ? 'bg-brand-500 text-white rounded-xl px-5 py-4 shadow-sm'
        : 'bg-white rounded-xl px-5 py-4 shadow-sm';

    let html = `
        <div class="w-9 h-9 rounded-full ${avatarColor} text-white flex items-center justify-center flex-shrink-0 text-sm font-semibold">${avatarText}</div>
        <div class="flex-1 max-w-3xl">
            <div class="${bubbleClass} leading-relaxed text-sm whitespace-pre-wrap">${escapeHtml(content)}</div>
    `;

    // Verified badge + sources for assistant
    if (!isUser && (sources?.length > 0 || verified)) {
        html += `<div class="mt-2 flex flex-wrap items-center gap-2">`;
        if (verified) html += verifiedBadge(true);
        if (confidence != null) {
            html += `<span class="text-xs text-gray-400">Confidence: ${(confidence * 100).toFixed(0)}%</span>`;
        }
        html += `</div>`;
    }

    // Source list
    if (sources && sources.length > 0) {
        html += `
            <div class="mt-3 p-3 bg-gray-50 rounded-lg text-xs">
                <p class="font-semibold text-gray-700 mb-2">Sources:</p>
                ${sources.map(s => `
                    <div class="py-1 flex items-center gap-2 text-gray-600">
                        ${jurisdictionBadge(s.jurisdiction, s.jurisdiction_label)}
                        <span class="truncate">${escapeHtml(s.content_preview || s.chunk_id)}</span>
                        <span class="text-gray-400 ml-auto flex-shrink-0">RRF: ${(s.rrf_score || 0).toFixed(3)}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    html += `</div>`;
    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function startNewChat() {
    currentConversationId = null;
    chatMessages.innerHTML = `
        <div class="welcome-message max-w-2xl mx-auto text-center py-12 px-6">
            <h3 class="text-2xl font-bold mb-4">Competition Law AI Assistant</h3>
            <p class="text-gray-500 leading-relaxed mb-2">Ask questions about <strong class="text-gray-900">Slovak and EU competition law</strong> in Slovak, Hungarian, or English.</p>
            <p class="text-gray-500 leading-relaxed">Sources include Slov-Lex, EUR-Lex, PMU decisions, and EU Commission decisions.</p>
            <div class="mt-8 p-6 bg-gray-50 rounded-xl text-left">
                <p class="font-semibold text-gray-700 mb-3">Example questions:</p>
                <p class="text-sm text-gray-600 py-1">SK: "Ake su hlavne zasady ochrany hospodarskej sutaze podla zakona 187/2021?"</p>
                <p class="text-sm text-gray-600 py-1">HU: "Mi a kartelltilalom lenyege az EU versenyjogban?"</p>
                <p class="text-sm text-gray-600 py-1">EN: "What is the difference between TFEU Article 101 and 102?"</p>
            </div>
        </div>
    `;
    showToast('New chat started', 'info');
}

// Search Functions
async function performSearch() {
    const query = searchInput.value.trim();
    if (!query) return;

    const jurisdiction = jurisdictionFilter.value || null;

    searchResults.innerHTML = '<div class="text-center py-10"><div class="spinner"></div></div>';
    searchBtn.disabled = true;

    try {
        const body = { query, top_k: 10 };
        if (jurisdiction) body.jurisdiction = jurisdiction;

        const response = await fetch(`${API_BASE_URL}/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (!response.ok) throw new Error('Search failed');

        const data = await response.json();
        displaySearchResults(data.results, data.language);

    } catch (error) {
        console.error('Error:', error);
        showToast('Search failed. Please try again.', 'error');
        searchResults.innerHTML = '<p class="text-center text-gray-400 py-10">Search failed.</p>';
    } finally {
        searchBtn.disabled = false;
    }
}

function displaySearchResults(results, language) {
    if (!results || results.length === 0) {
        searchResults.innerHTML = '<p class="text-center text-gray-400 py-10">No results found.</p>';
        return;
    }

    searchResults.innerHTML = results.map(r => `
        <div class="bg-white p-6 rounded-xl mb-4 shadow-sm hover:shadow-md transition-shadow">
            <div class="flex justify-between items-start mb-3">
                <div class="flex items-center gap-2">
                    ${jurisdictionBadge(r.jurisdiction, r.jurisdiction_label)}
                    <span class="text-sm font-semibold text-brand-500">${escapeHtml(r.metadata?.filename || r.document_id)}</span>
                </div>
                <span class="text-xs px-2 py-1 bg-gray-100 rounded font-mono">RRF: ${(r.rrf_score || 0).toFixed(3)}</span>
            </div>
            <p class="text-sm leading-relaxed text-gray-700 mb-3">${escapeHtml(r.content)}</p>
            <div class="text-xs text-gray-400">
                ${r.metadata?.language ? r.metadata.language.toUpperCase() : ''} | chunk: ${r.chunk_id}
            </div>
        </div>
    `).join('');
}

// Document Functions
async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE_URL}/documents`);
        if (!response.ok) throw new Error('Failed to load documents');

        const documents = await response.json();
        displayDocuments(documents);

    } catch (error) {
        console.error('Error loading documents:', error);
    }
}

function displayDocuments(documents) {
    if (!documents || documents.length === 0) return;

    documentsList.innerHTML = documents.map(doc => `
        <div class="bg-white p-5 rounded-xl mb-3 shadow-sm hover:shadow-md transition-shadow flex justify-between items-center">
            <div>
                <h3 class="text-sm font-semibold mb-1">${escapeHtml(doc.filename)}</h3>
                <div class="text-xs text-gray-400 flex items-center gap-2">
                    ${jurisdictionBadge(doc.jurisdiction)}
                    <span>${(doc.language || '').toUpperCase()}</span>
                    <span>|</span>
                    <span>${doc.document_type}</span>
                    <span>|</span>
                    <span>${doc.chunk_count || 0} chunks</span>
                    <span>|</span>
                    <span>${doc.upload_date ? new Date(doc.upload_date).toLocaleDateString() : ''}</span>
                </div>
            </div>
            <button class="p-2 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 transition-all" onclick="deleteDocument('${doc.id}')" title="Delete">
                <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z"/>
                </svg>
            </button>
        </div>
    `).join('');
}

async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', 'legal');

    showToast('Uploading document...', 'info');

    try {
        const response = await fetch(`${API_BASE_URL}/documents/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Upload failed');

        const data = await response.json();
        showToast(`"${data.filename}" uploaded (${data.chunks_processed} chunks)`, 'success');
        await loadDocuments();

    } catch (error) {
        console.error('Error:', error);
        showToast('Upload failed. Please try again.', 'error');
    } finally {
        fileInput.value = '';
    }
}

async function deleteDocument(documentId) {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
        const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Delete failed');

        showToast('Document deleted', 'success');
        await loadDocuments();

    } catch (error) {
        console.error('Error:', error);
        showToast('Failed to delete document', 'error');
    }
}

// Toast Notifications
function showToast(message, type = 'info') {
    const colors = {
        success: 'border-l-4 border-emerald-500',
        error: 'border-l-4 border-red-500',
        info: 'border-l-4 border-brand-500',
    };
    const toast = document.createElement('div');
    toast.className = `toast-animate bg-white px-5 py-4 rounded-lg shadow-lg mb-3 min-w-[280px] text-sm ${colors[type] || colors.info}`;
    toast.textContent = message;

    document.getElementById('toastContainer').appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Utility
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================
// Judge Assistant
// ============================================================

async function runJudgeAnalysis() {
    const caseDescription = judgeInput.value.trim();
    if (!caseDescription || caseDescription.length < 50) {
        showToast('Please enter a case description (minimum 50 characters).', 'error');
        return;
    }

    const language = judgeLanguage.value || undefined;

    // Show progress, hide result
    judgeSubmitBtn.disabled = true;
    judgeProgress.classList.remove('hidden');
    judgeResultPanel.classList.add('hidden');

    // Animate step 1 immediately (topic definition happens server-side first)
    _setStepState(1, 'active');

    try {
        const body = { case_description: caseDescription };
        if (language) body.language = language;

        const response = await fetch(`${API_BASE_URL}/judge/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP ${response.status}`);
        }

        // Animate remaining steps while waiting (the server runs them sequentially)
        await _animateSteps();

        const data = await response.json();

        judgeProgress.classList.add('hidden');
        displayJudgeResult(data);

    } catch (error) {
        console.error('Judge analysis error:', error);
        judgeProgress.classList.add('hidden');
        showToast(`Analysis failed: ${error.message}`, 'error');
        _resetStepStates();
    } finally {
        judgeSubmitBtn.disabled = false;
    }
}

/** Animate the 4 step rows with delays to give visual feedback during the long request. */
async function _animateSteps() {
    const delays = [0, 4000, 12000, 20000]; // approximate times for each step
    for (let i = 1; i <= 4; i++) {
        await new Promise(resolve => setTimeout(resolve, i === 1 ? 0 : delays[i - 1]));
        _setStepState(i, 'active');
        if (i > 1) _setStepState(i - 1, 'done');
    }
}

function _setStepState(stepNum, state) {
    const row = document.getElementById(`step${stepNum}row`);
    if (!row) return;
    const icon = row.querySelector('.step-icon');

    icon.classList.remove(
        'border-gray-200', 'text-gray-400',
        'border-brand-500', 'text-brand-500', 'bg-brand-50',
        'border-emerald-500', 'bg-emerald-500', 'text-white',
    );

    if (state === 'active') {
        icon.classList.add('border-brand-500', 'text-brand-500', 'bg-brand-50');
    } else if (state === 'done') {
        icon.classList.add('border-emerald-500', 'bg-emerald-500', 'text-white');
        icon.innerHTML = `<svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/>
        </svg>`;
    } else {
        icon.classList.add('border-gray-200', 'text-gray-400');
    }
}

function _resetStepStates() {
    for (let i = 1; i <= 4; i++) {
        const row = document.getElementById(`step${i}row`);
        if (!row) continue;
        const icon = row.querySelector('.step-icon');
        icon.classList.remove(
            'border-brand-500', 'text-brand-500', 'bg-brand-50',
            'border-emerald-500', 'bg-emerald-500', 'text-white',
        );
        icon.classList.add('border-gray-200', 'text-gray-400');
        icon.textContent = String(i);
    }
}

function resetJudgeView() {
    judgeResultPanel.classList.add('hidden');
    judgeProgress.classList.add('hidden');
    _resetStepStates();
    judgeInput.value = '';
    judgeInput.focus();
}

function displayJudgeResult(data) {
    // ── Step 1: Topic ────────────────────────────────────────────────────────
    const topic = data.topic || {};
    const issues = (topic.legal_issues || []).map(i => `<li class="text-sm text-gray-700">${escapeHtml(i)}</li>`).join('');
    const keywords = (topic.search_keywords || []).map(k =>
        `<span class="px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600">${escapeHtml(k)}</span>`
    ).join('');
    const jurisdictions = (topic.jurisdictions || []).map(j => jurisdictionBadge(j)).join(' ');

    document.getElementById('judgeTopicSection').innerHTML = `
        <div class="grid grid-cols-2 gap-4 mb-4">
            <div>
                <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Legal Domain</p>
                <p class="text-sm font-medium text-gray-800">${escapeHtml(topic.legal_domain || '—')}</p>
            </div>
            <div>
                <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Jurisdictions</p>
                <div class="flex gap-1.5">${jurisdictions || '—'}</div>
            </div>
        </div>
        <div class="mb-4">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Topic Summary</p>
            <p class="text-sm text-gray-700 leading-relaxed">${escapeHtml(topic.topic_summary || '—')}</p>
        </div>
        <div class="mb-4">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Key Legal Issues</p>
            <ul class="list-disc list-inside space-y-1">${issues || '<li class="text-sm text-gray-400">None identified</li>'}</ul>
        </div>
        <div>
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Search Keywords Used</p>
            <div class="flex flex-wrap gap-2">${keywords || '<span class="text-sm text-gray-400">—</span>'}</div>
        </div>
    `;

    // ── Step 2: Sources ───────────────────────────────────────────────────────
    const sources = data.case_law_sources || [];
    document.getElementById('judgeSourceCount').textContent =
        sources.length > 0 ? `${sources.length} result${sources.length !== 1 ? 's' : ''}` : 'No results';

    if (sources.length === 0) {
        document.getElementById('judgeSourcesSection').innerHTML =
            '<p class="text-sm text-gray-400">No case law was retrieved from the external databases for this topic.</p>';
    } else {
        const grouped = { SK: [], EU: [] };
        sources.forEach(s => {
            (grouped[s.jurisdiction] || grouped['EU']).push(s);
        });

        const renderGroup = (label, items) => {
            if (!items.length) return '';
            return `
                <div class="mb-4">
                    <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">${escapeHtml(label)}</p>
                    <div class="flex flex-col gap-2">
                        ${items.map(s => `
                            <div class="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                                ${jurisdictionBadge(s.jurisdiction)}
                                <div class="flex-1 min-w-0">
                                    <p class="text-sm font-medium text-gray-800 truncate">${escapeHtml(s.title || s.case_number || '—')}</p>
                                    <div class="flex items-center gap-2 mt-0.5 text-xs text-gray-400">
                                        ${s.case_number ? `<span>${escapeHtml(s.case_number)}</span>` : ''}
                                        ${s.date ? `<span>· ${escapeHtml(s.date)}</span>` : ''}
                                        ${s.source ? `<span>· ${escapeHtml(s.source)}</span>` : ''}
                                    </div>
                                </div>
                                ${s.url ? `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener" class="flex-shrink-0 text-brand-500 hover:text-brand-700 text-xs font-medium">View →</a>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        };

        document.getElementById('judgeSourcesSection').innerHTML =
            renderGroup('Slovak Judicial Decisions [SK] · Slov-lex', grouped.SK) +
            renderGroup('EU Case Law & Decisions [EU] · EC / CJEU', grouped.EU);
    }

    // ── Step 3: Case law analysis ─────────────────────────────────────────────
    document.getElementById('judgeCaseLawSection').innerHTML =
        `<div class="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">${escapeHtml(data.case_law_analysis || '—')}</div>`;

    // ── Step 4: Final analysis ────────────────────────────────────────────────
    // Render markdown-style headings (## I. ...) as styled HTML
    const finalText = data.final_analysis || '—';
    document.getElementById('judgeFinalSection').innerHTML =
        `<div class="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">${renderLegalText(finalText)}</div>`;

    // Show results, hide input form
    judgeResultPanel.classList.remove('hidden');
    judgeResultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Light renderer: converts ## headings and [SK]/[EU] labels to styled HTML.
 * Keeps whitespace-pre-wrap, just adds colour to headings and badges.
 */
function renderLegalText(text) {
    return escapeHtml(text)
        // ## heading → bold coloured line
        .replace(/^(##\s+.+)$/gm, '<strong class="text-gray-900 block mt-4 mb-1">$1</strong>')
        // [EU] and [SK] inline labels → coloured badges
        .replace(/\[EU\]/g, '<span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300 mx-0.5">[EU]</span>')
        .replace(/\[SK\]/g, '<span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300 mx-0.5">[SK]</span>');
}

// Expose to global scope (needed for inline onclick handlers in dynamic HTML)
window.deleteDocument = deleteDocument;
