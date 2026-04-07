<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../api/client.js';
  import DOMPurify from 'dompurify';

  // ── State ──
  let currentView = 'inbox'; // 'inbox' | 'compose' | 'read'
  let currentFolder = 'inbox';
  let messages = [];
  let selectedMessage = null;
  let labels = [];
  let unreadCount = 0;
  let loading = true;
  let gmailConnected = false;
  let hasScope = false;
  let searchQuery = '';
  let nextPageToken = null;
  let loadingMore = false;

  // Folder cache — keep messages per folder in memory
  let folderCache = {};
  let folderPageTokens = {};

  // Auto-refresh
  let refreshInterval;

  // Compose form
  let composeForm = { to: '', cc: '', subject: '', body: '' };
  let composeFiles = [];
  let replyToId = null;
  let sending = false;

  // Inline reply
  let showInlineReply = false;
  let inlineReplyText = '';
  let inlineReplyFiles = [];

  // Gmail signature
  let gmailSignature = '';

  // Selection
  let selectedIds = new Set();
  let selectAll = false;

  // ── Folders ──
  const FOLDERS = [
    { key: 'inbox', label: 'Inbox', svg: '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>' },
    { key: 'sent', label: 'Envoyes', svg: '<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>' },
    { key: 'starred', label: 'Favoris', svg: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>' },
    { key: 'draft', label: 'Brouillons', svg: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>' },
    { key: 'important', label: 'Important', svg: '<path d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z"/><circle cx="6" cy="6" r="1"/>' },
    { key: 'trash', label: 'Corbeille', svg: '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>' },
  ];

  const CATEGORIES = [
    { label: 'Travail', color: '#3B82F6' },
    { label: 'Personnel', color: '#22C55E' },
    { label: 'Support', color: '#F59E0B' },
    { label: 'Social', color: '#EC4899' },
  ];

  function toggleSelectAll() {
    if (selectAll) {
      selectedIds = new Set();
    } else {
      selectedIds = new Set(messages.map(m => m.id));
    }
    selectAll = !selectAll;
    selectedIds = selectedIds;
  }

  function toggleSelect(msgId, e) {
    e.stopPropagation();
    if (selectedIds.has(msgId)) selectedIds.delete(msgId);
    else selectedIds.add(msgId);
    selectedIds = selectedIds;
    selectAll = selectedIds.size === messages.length;
  }

  async function trashSelected() {
    for (const id of selectedIds) {
      try { await api.post(`/api/gmail/messages/${id}/trash`); } catch {}
    }
    messages = messages.filter(m => !selectedIds.has(m.id));
    selectedIds = new Set();
    selectAll = false;
  }

  // ── Helpers ──
  function parseFromName(from) {
    if (!from) return 'Inconnu';
    // Format: "Name" <email> or Name <email> or just email@domain
    const match = from.match(/^"?([^"<]+?)"?\s*</) || from.match(/^([^<@]+)/);
    if (match) {
      const name = match[1].trim();
      return name || from.split('@')[0] || 'Inconnu';
    }
    return from.split('@')[0] || 'Inconnu';
  }

  function parseFromEmail(from) {
    if (!from) return '';
    const match = from.match(/<([^>]+)>/);
    return match ? match[1] : from;
  }

  function getInitials(name) {
    return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  }

  function getInitialColor(name) {
    let hash = 0;
    for (const c of name) hash = c.charCodeAt(0) + ((hash << 5) - hash);
    const colors = ['#8869e1', '#F59E0B', '#3A9B94', '#EC4899', '#3B82F6', '#EF4444', '#22C55E'];
    return colors[Math.abs(hash) % colors.length];
  }

  function formatDate(internalDate) {
    if (!internalDate) return '';
    const d = new Date(Number(internalDate));
    const now = new Date();
    const diffMs = now - d;
    const diffH = diffMs / 3600000;

    if (diffH < 1) return `${Math.floor(diffMs / 60000)}min`;
    if (diffH < 24 && d.getDate() === now.getDate()) {
      return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    }
    if (diffH < 168) { // < 7 days
      return d.toLocaleDateString('fr-FR', { weekday: 'short' });
    }
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
  }

  function formatFullDate(dateStr) {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return dateStr; }
  }

  // ── API calls ──
  async function checkStatus() {
    try {
      const s = await api.get('/api/gmail/status');
      gmailConnected = s.connected;
      hasScope = s.has_scope;
    } catch {
      gmailConnected = false;
      hasScope = false;
    }
  }

  async function fetchMessages(force = false) {
    // Use cache if available and not forced
    if (!force && folderCache[currentFolder] && !searchQuery) {
      messages = folderCache[currentFolder];
      nextPageToken = folderPageTokens[currentFolder] || null;
      loading = false;
      return;
    }
    loading = true;
    try {
      const params = `folder=${currentFolder}&max_results=50${searchQuery ? `&q=${encodeURIComponent(searchQuery)}` : ''}`;
      const data = await api.get(`/api/gmail/messages?${params}`);
      messages = data.messages || [];
      nextPageToken = data.nextPageToken;
      // Cache results (not search queries)
      if (!searchQuery) {
        folderCache[currentFolder] = messages;
        folderPageTokens[currentFolder] = nextPageToken;
      }
    } catch (e) {
      console.error('Failed to fetch messages', e);
      messages = [];
    }
    loading = false;
  }

  async function loadMore() {
    if (!nextPageToken || loadingMore) return;
    loadingMore = true;
    try {
      const params = `folder=${currentFolder}&max_results=50&page_token=${nextPageToken}${searchQuery ? `&q=${encodeURIComponent(searchQuery)}` : ''}`;
      const data = await api.get(`/api/gmail/messages?${params}`);
      messages = [...messages, ...(data.messages || [])];
      nextPageToken = data.nextPageToken;
      if (!searchQuery) {
        folderCache[currentFolder] = messages;
        folderPageTokens[currentFolder] = nextPageToken;
      }
    } catch {}
    loadingMore = false;
  }

  async function fetchSignature() {
    try {
      const { signature } = await api.get('/api/gmail/signature');
      gmailSignature = signature || '';
    } catch { gmailSignature = ''; }
  }

  // Silent refresh is now handled by triggerSync() in the interval

  async function fetchUnreadCount() {
    try {
      const { count } = await api.get('/api/gmail/unread-count');
      unreadCount = count;
    } catch { unreadCount = 0; }
  }

  async function openMessage(msg) {
    try {
      selectedMessage = await api.get(`/api/gmail/messages/${msg.id}`);
      currentView = 'read';
      if (msg.unread) {
        // Update UI instantly
        msg.unread = false;
        messages = messages;
        unreadCount = Math.max(0, unreadCount - 1);
        // Then tell backend (fire & forget)
        api.post(`/api/gmail/messages/${msg.id}/read`).catch(() => {});
      }
    } catch (e) {
      console.error('Failed to open message', e);
    }
  }

  async function toggleStar(msg, e) {
    e.stopPropagation();
    const newStarred = !msg.starred;
    try {
      await api.post(`/api/gmail/messages/${msg.id}/star?starred=${newStarred}`);
      msg.starred = newStarred;
      messages = messages;
    } catch {}
  }

  async function trashMessage(msg, e) {
    if (e) e.stopPropagation();
    try {
      await api.post(`/api/gmail/messages/${msg.id}/trash`);
      messages = messages.filter(m => m.id !== msg.id);
      if (selectedMessage?.id === msg.id) {
        currentView = 'inbox';
        selectedMessage = null;
      }
    } catch {}
  }

  async function sendEmail() {
    sending = true;
    try {
      const bodyWithSig = gmailSignature
        ? `${composeForm.body}\n\n${gmailSignature}`
        : composeForm.body;

      if (composeFiles.length > 0) {
        // Send with attachments via multipart form
        const fd = new FormData();
        fd.append('to', composeForm.to);
        fd.append('subject', composeForm.subject);
        fd.append('body', bodyWithSig);
        fd.append('cc', composeForm.cc || '');
        fd.append('bcc', '');
        fd.append('reply_to_message_id', replyToId || '');
        for (const f of composeFiles) fd.append('files', f);
        await fetch('http://localhost:8010/api/gmail/send-with-attachments', { method: 'POST', body: fd });
      } else {
        const payload = { ...composeForm, body: bodyWithSig };
        if (replyToId) payload.reply_to_message_id = replyToId;
        await api.post('/api/gmail/send', payload);
      }
      composeForm = { to: '', cc: '', subject: '', body: '' };
      composeFiles = [];
      replyToId = null;
      currentView = 'inbox';
      folderCache = {};
      // Sync immediately to pickup the sent message
      await triggerSync();
      await fetchMessages(true);
    } catch (e) {
      console.error('Failed to send', e);
    }
    sending = false;
  }

  async function sendInlineReply() {
    if (!inlineReplyText.trim() || !selectedMessage) return;
    sending = true;
    try {
      const bodyWithSig = gmailSignature
        ? `${inlineReplyText}\n\n${gmailSignature}`
        : inlineReplyText;

      if (inlineReplyFiles.length > 0) {
        const fd = new FormData();
        fd.append('to', parseFromEmail(selectedMessage.from));
        fd.append('subject', `Re: ${selectedMessage.subject}`);
        fd.append('body', bodyWithSig);
        fd.append('cc', '');
        fd.append('bcc', '');
        fd.append('reply_to_message_id', selectedMessage.id);
        for (const f of inlineReplyFiles) fd.append('files', f);
        await fetch('http://localhost:8010/api/gmail/send-with-attachments', { method: 'POST', body: fd });
      } else {
        await api.post('/api/gmail/send', {
          to: parseFromEmail(selectedMessage.from),
          subject: `Re: ${selectedMessage.subject}`,
          body: bodyWithSig,
          reply_to_message_id: selectedMessage.id,
        });
      }
      inlineReplyText = '';
      inlineReplyFiles = [];
      showInlineReply = false;
    } catch (e) {
      console.error('Failed to send reply', e);
    }
    sending = false;
  }

  function handleInlineReplyFiles(e) {
    inlineReplyFiles = [...inlineReplyFiles, ...Array.from(e.target.files)];
  }

  function removeInlineReplyFile(index) {
    inlineReplyFiles = inlineReplyFiles.filter((_, i) => i !== index);
  }

  function openCompose(replyMsg = null) {
    composeForm = { to: '', cc: '', subject: '', body: '' };
    composeFiles = [];
    replyToId = null;
    if (replyMsg) {
      composeForm.to = parseFromEmail(replyMsg.from);
      composeForm.subject = `Re: ${replyMsg.subject}`;
      replyToId = replyMsg.id;
    }
    currentView = 'compose';
  }

  function handleFileSelect(e) {
    composeFiles = [...composeFiles, ...Array.from(e.target.files)];
  }

  function removeFile(index) {
    composeFiles = composeFiles.filter((_, i) => i !== index);
  }

  function switchFolder(folder) {
    currentFolder = folder;
    currentView = 'inbox';
    selectedMessage = null;
    showInlineReply = false;
    searchQuery = '';
    fetchMessages(); // Will use cache if available
  }

  function backToInbox() {
    currentView = 'inbox';
    selectedMessage = null;
    showInlineReply = false;
  }

  async function downloadAttachment(msgId, attId, filename) {
    try {
      const resp = await fetch(`http://localhost:8010/api/gmail/messages/${msgId}/attachments/${attId}?filename=${encodeURIComponent(filename)}`);
      if (!resp.ok) throw new Error('Download failed: ' + resp.status);
      const blob = await resp.blob();
      const arrayBuf = await blob.arrayBuffer();
      const bytes = new Uint8Array(arrayBuf);

      // Try Tauri save dialog
      try {
        const { save } = await import('@tauri-apps/plugin-dialog');
        const { writeBinaryFile } = await import('@tauri-apps/plugin-fs');
        const path = await save({
          defaultPath: filename,
          filters: [{ name: 'Fichier', extensions: [filename.split('.').pop() || '*'] }],
        });
        if (path) {
          await writeBinaryFile(path, bytes);
        }
      } catch (tauriErr) {
        console.warn('Tauri save failed, using browser fallback:', tauriErr);
        // Fallback: browser download
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    } catch (e) {
      console.error('Failed to download attachment', e);
    }
  }

  async function previewAttachment(msgId, attId, filename, mimeType) {
    try {
      const resp = await fetch(`http://localhost:8010/api/gmail/messages/${msgId}/attachments/${attId}?filename=${encodeURIComponent(filename)}`);
      if (!resp.ok) throw new Error('Preview failed');
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);

      // Open in new window for preview
      if (mimeType?.startsWith('image/') || mimeType === 'application/pdf') {
        window.open(url, '_blank');
      } else {
        // For non-previewable files, trigger download
        await downloadAttachment(msgId, attId, filename);
      }
    } catch (e) {
      console.error('Preview failed', e);
    }
  }

  let syncing = false;
  let syncStatus = null;

  async function triggerSync(full = false) {
    syncing = true;
    try {
      const endpoint = full ? '/api/gmail/sync/full' : '/api/gmail/sync';
      await api.post(endpoint);
    } catch (e) {
      console.error('Sync failed', e);
    }
    syncing = false;
    // Refresh current view from cache
    await fetchMessages(true);
    await fetchUnreadCount();
  }

  // ── Lifecycle ──
  onMount(async () => {
    await checkStatus();
    if (gmailConnected && hasScope) {
      // Load from cache first (instant)
      await Promise.all([fetchMessages(true), fetchUnreadCount(), fetchSignature()]);
      // Then sync in background (non-blocking)
      triggerSync();
      // Auto-sync every 30 seconds
      refreshInterval = setInterval(() => triggerSync(), 30000);
    } else {
      loading = false;
    }
  });

  onDestroy(() => {
    if (refreshInterval) clearInterval(refreshInterval);
  });
</script>

<div class="email-page">
  <!-- ═══ Sidebar — YashAdmin style ═══ -->
  <div class="email-sidebar">
    <button class="compose-btn" on:click={() => openCompose()}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      Compose Email
    </button>

    <div class="email-folders">
      {#each FOLDERS as f}
        <button
          class="folder-item"
          class:folder-item--active={currentFolder === f.key && currentView !== 'compose'}
          on:click={() => switchFolder(f.key)}
        >
          <span class="folder-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">{@html f.svg}</svg>
          </span>
          <span class="folder-label">{f.label}</span>
          {#if f.key === 'inbox' && unreadCount > 0}
            <span class="folder-badge">{unreadCount}</span>
          {/if}
        </button>
      {/each}
    </div>

    <div class="sidebar-divider"></div>
    <div class="sidebar-categories">
      <h6 class="categories-title">Categories</h6>
      {#each CATEGORIES as cat}
        <button class="cat-item" on:click={() => { searchQuery = `category:${cat.label.toLowerCase()}`; fetchMessages(); }}>
          <span class="cat-dot" style="background:{cat.color}"></span>
          {cat.label}
        </button>
      {/each}
    </div>
  </div>

  <!-- ═══ Content ═══ -->
  <div class="email-content">
    {#if !gmailConnected || !hasScope}
      <!-- Not connected -->
      <div class="email-empty">
        <h3>Email non connecte</h3>
        <p>Allez dans Parametres > Integrations > Google Calendar et reconnectez-vous pour activer Gmail.</p>
      </div>

    {:else if currentView === 'inbox'}
      <!-- ── Inbox — YashAdmin toolbar with icons ── -->
      <div class="email-toolbar">
        <div class="toolbar-left">
          <!-- Select all checkbox -->
          <button class="toolbar-checkbox" on:click={toggleSelectAll}>
            {#if selectAll}
              <svg width="16" height="16" viewBox="0 0 18 18" fill="none"><rect x="1" y="1" width="16" height="16" rx="3" fill="var(--primary)" stroke="var(--primary)" stroke-width="1.5"/><path d="M5 9l2.5 2.5L13 6" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            {:else}
              <svg width="16" height="16" viewBox="0 0 18 18" fill="none"><rect x="1" y="1" width="16" height="16" rx="3" stroke="var(--border-subtle)" stroke-width="1.5"/></svg>
            {/if}
          </button>

          <!-- Tabs — YashAdmin style -->
          <div class="toolbar-tabs">
            <button class="toolbar-tab" class:toolbar-tab--active={currentFolder === 'inbox'} on:click={() => switchFolder('inbox')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/></svg>
              Important
            </button>
            <button class="toolbar-tab" on:click={() => { searchQuery = 'category:social'; fetchMessages(); }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
              Socials
            </button>
            <button class="toolbar-tab" on:click={() => { searchQuery = 'category:promotions'; fetchMessages(); }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>
              Promotion
            </button>
          </div>
        </div>

        <div class="toolbar-right">
          <!-- Action icons — YashAdmin style -->
          {#if selectedIds.size > 0}
            <button class="toolbar-icon" on:click={trashSelected} title="Supprimer la selection">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
            </button>
          {/if}
          <button class="toolbar-icon" on:click={() => fetchMessages()} title="Rafraichir">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 12a10 10 0 0118-6M22 12a10 10 0 01-18 6"/></svg>
          </button>
          <div class="toolbar-separator"></div>
          <input
            type="text"
            class="email-search"
            placeholder="Rechercher..."
            bind:value={searchQuery}
            on:keydown={(e) => e.key === 'Enter' && fetchMessages()}
          />
        </div>
      </div>

      {#if loading}
        <div class="email-loading">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2" class="spin"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>
          Chargement...
        </div>
      {:else if messages.length === 0}
        <div class="email-empty">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1" style="opacity:0.4"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
          <p style="margin-top:1rem">Aucun message dans ce dossier</p>
        </div>
      {:else}
        <div class="email-list">
          {#each messages as msg (msg.id)}
            <div
              class="msg-row"
              class:msg-row--unread={msg.unread}
              class:msg-row--selected={selectedIds.has(msg.id)}
              on:click={() => openMessage(msg)}
            >
              <!-- Checkbox -->
              <button class="msg-check" on:click={(e) => toggleSelect(msg.id, e)}>
                {#if selectedIds.has(msg.id)}
                  <svg width="16" height="16" viewBox="0 0 18 18" fill="none"><rect x="1" y="1" width="16" height="16" rx="3" fill="var(--primary)" stroke="var(--primary)" stroke-width="1.5"/><path d="M5 9l2.5 2.5L13 6" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                {:else}
                  <svg width="16" height="16" viewBox="0 0 18 18" fill="none"><rect x="1" y="1" width="16" height="16" rx="3" stroke="var(--border-subtle)" stroke-width="1.5"/></svg>
                {/if}
              </button>

              <!-- Star -->
              <button class="msg-star" on:click={(e) => toggleStar(msg, e)}>
                {#if msg.starred}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="#F8B940" stroke="#F8B940" stroke-width="1"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                {:else}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                {/if}
              </button>

              <!-- Sender -->
              <div class="msg-sender" class:msg-sender--bold={msg.unread}>
                {parseFromName(msg.from)}
              </div>

              <!-- Subject + snippet + PJ chips -->
              <div class="msg-content-col">
                <div class="msg-content">
                  {#if msg.hasAttachments}
                    <span class="msg-pj" title="Pieces jointes">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
                    </span>
                  {/if}
                  <span class="msg-subject" class:msg-subject--bold={msg.unread}>{msg.subject}</span>
                  <span class="msg-snippet"> — {msg.snippet}</span>
                </div>
                {#if msg.attachmentNames?.length > 0}
                  <div class="msg-att-chips">
                    {#each msg.attachmentNames.slice(0, 3) as name}
                      <span class="msg-att-chip">
                        {#if name.match(/\.(pdf)$/i)}
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                        {:else if name.match(/\.(jpg|jpeg|png|gif|webp)$/i)}
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                        {:else}
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                        {/if}
                        {name.length > 20 ? name.slice(0, 17) + '...' : name}
                      </span>
                    {/each}
                  </div>
                {/if}
              </div>

              <!-- Date -->
              <div class="msg-date">{formatDate(msg.internalDate)}</div>

              <!-- Hover actions -->
              <div class="msg-hover-actions">
                <button class="msg-hover-btn" on:click={(e) => trashMessage(msg, e)} title="Supprimer">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
                </button>
              </div>
            </div>
          {/each}

          {#if nextPageToken}
            <button class="load-more-btn" on:click={loadMore} disabled={loadingMore}>
              {loadingMore ? 'Chargement...' : 'Charger plus'}
            </button>
          {/if}
        </div>
      {/if}

    {:else if currentView === 'compose'}
      <!-- ── Compose view — YashAdmin style ── -->
      <div class="compose-view">
        <div class="compose-field">
          <input type="text" placeholder="To:" bind:value={composeForm.to} />
        </div>
        <div class="compose-field">
          <input type="text" placeholder="Cc:" bind:value={composeForm.cc} />
        </div>
        <div class="compose-field">
          <input type="text" placeholder="Subject:" bind:value={composeForm.subject} />
        </div>
        <div class="compose-field compose-body">
          <textarea placeholder="Ecrivez votre message..." bind:value={composeForm.body} rows="12"></textarea>
        </div>

        <div class="compose-attachment-section">
          <h5 class="compose-attachment-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
            Pieces jointes
          </h5>

          {#if composeFiles.length > 0}
            <div class="compose-file-list">
              {#each composeFiles as f, i}
                <div class="compose-file-item">
                  <span class="compose-file-name">{f.name}</span>
                  <span class="compose-file-size">({Math.round(f.size / 1024)}Ko)</span>
                  <button class="compose-file-remove" on:click={() => removeFile(i)}>&times;</button>
                </div>
              {/each}
            </div>
          {/if}

          <label class="compose-file-drop">
            <input type="file" multiple on:change={handleFileSelect} style="display:none" />
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            Ajouter des fichiers
          </label>
        </div>

        <div class="compose-actions">
          <button class="ya-btn ya-btn--primary compose-send-btn" on:click={sendEmail} disabled={sending || !composeForm.to || !composeForm.subject}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            {sending ? 'Envoi...' : 'Envoyer'}
          </button>
          <button class="ya-btn discard-btn" on:click={backToInbox}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            Annuler
          </button>
        </div>
      </div>

    {:else if currentView === 'read' && selectedMessage}
      <!-- ── Read view ── -->
      <div class="read-view">
        <div class="read-toolbar">
          <button class="toolbar-btn" on:click={backToInbox}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
            Retour
          </button>
          <div class="read-actions">
            <button class="toolbar-btn" on:click={() => openCompose(selectedMessage)} title="Repondre">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 17 4 12 9 7"/><path d="M20 18v-2a4 4 0 00-4-4H4"/></svg>
            </button>
            <button class="toolbar-btn" on:click={(e) => trashMessage(selectedMessage, e)} title="Supprimer">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
            </button>
          </div>
        </div>

        <div class="read-header">
          <div class="read-avatar" style="background:{getInitialColor(parseFromName(selectedMessage.from))}">
            {getInitials(parseFromName(selectedMessage.from))}
          </div>
          <div class="read-meta">
            <h4 class="read-from">{parseFromName(selectedMessage.from)}</h4>
            <span class="read-email">{parseFromEmail(selectedMessage.from)}</span>
          </div>
          <div class="read-date">{formatFullDate(selectedMessage.date)}</div>
        </div>

        <h3 class="read-subject">{selectedMessage.subject}</h3>

        <div class="read-body">
          {#if selectedMessage.body_html}
            {@html DOMPurify.sanitize(selectedMessage.body_html)}
          {:else}
            <pre class="read-body-text">{selectedMessage.body_text || ''}</pre>
          {/if}
        </div>

        {#if selectedMessage.attachments?.length > 0}
          <div class="read-attachments">
            <h5>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              Pieces jointes ({selectedMessage.attachments.length})
            </h5>
            <div class="att-list">
              {#each selectedMessage.attachments as att}
                <div class="att-card">
                  <div class="att-card__icon">
                    {#if att.mimeType?.startsWith('image/')}
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                    {:else if att.mimeType === 'application/pdf'}
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    {:else}
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    {/if}
                  </div>
                  <div class="att-card__info">
                    <span class="att-card__name">{att.filename}</span>
                    <span class="att-card__size">{Math.round(att.size / 1024)} Ko</span>
                  </div>
                  {#if att.attachmentId}
                    <div class="att-card__actions">
                      {#if att.mimeType?.startsWith('image/') || att.mimeType === 'application/pdf'}
                        <button
                          class="att-card__btn"
                          on:click={() => previewAttachment(selectedMessage.id, att.attachmentId, att.filename, att.mimeType)}
                          title="Visualiser"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        </button>
                      {/if}
                      <button
                        class="att-card__btn"
                        on:click={() => downloadAttachment(selectedMessage.id, att.attachmentId, att.filename)}
                        title="Telecharger"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                      </button>
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <hr style="border-color:var(--border-subtle);margin:1.5rem 0" />

        <!-- Inline reply — YashAdmin style -->
        <div class="inline-reply">
          <textarea
            class="inline-reply-textarea"
            placeholder="Ecrire une reponse..."
            bind:value={inlineReplyText}
            on:focus={() => showInlineReply = true}
            rows={showInlineReply ? 5 : 2}
          ></textarea>
          {#if showInlineReply}
            <!-- Inline reply files -->
            {#if inlineReplyFiles.length > 0}
              <div class="compose-file-list" style="margin-top:0.5rem">
                {#each inlineReplyFiles as f, i}
                  <div class="compose-file-item">
                    <span class="compose-file-name">{f.name}</span>
                    <span class="compose-file-size">({Math.round(f.size / 1024)}Ko)</span>
                    <button class="compose-file-remove" on:click={() => removeInlineReplyFile(i)}>&times;</button>
                  </div>
                {/each}
              </div>
            {/if}
            <div class="inline-reply-actions">
              <label class="inline-reply-attach" title="Ajouter une piece jointe">
                <input type="file" multiple on:change={handleInlineReplyFiles} style="display:none" />
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
              </label>
              <button class="ya-btn ya-btn--primary" on:click={sendInlineReply} disabled={sending || !inlineReplyText.trim()}>
                {sending ? 'Envoi...' : 'Envoyer'}
              </button>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  /* ── Email page layout ── */
  .email-page {
    display: flex;
    gap: 0;
    animation: fadeIn 0.3s ease-out;
    margin: -1.875rem;
    min-height: calc(100vh - 70px);
  }

  /* ── Sidebar ── */
  .email-sidebar {
    width: 260px;
    flex-shrink: 0;
    background: var(--bg-card);
    border-right: 1px solid var(--border-subtle);
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .compose-btn {
    width: 100%;
    padding: 0.75rem 1rem;
    background: var(--primary);
    color: #fff !important;
    border: none;
    border-radius: 0.625rem;
    font-size: 0.9375rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    transition: filter 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
  }

  .compose-btn:hover { filter: brightness(1.1); }

  .email-folders {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .folder-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.625rem 1rem;
    background: none;
    border: none;
    border-radius: 0.375rem;
    font-size: 0.9375rem;
    font-weight: 500;
    color: var(--text-primary);
    cursor: pointer;
    font-family: inherit;
    text-align: left;
    transition: all 0.1s;
    width: 100%;
  }

  .folder-item:hover {
    background: rgba(var(--primary-rgb), 0.08);
  }

  .folder-item--active {
    background: rgba(var(--primary-rgb), 0.12) !important;
    color: var(--primary) !important;
    font-weight: 600;
  }

  .folder-icon {
    display: flex;
    flex-shrink: 0;
    opacity: 0.7;
  }

  .folder-item--active .folder-icon { opacity: 1; }

  .folder-label { flex: 1; }

  .folder-badge {
    background: var(--primary) !important;
    color: #fff !important;
    font-size: 0.6875rem;
    font-weight: 600;
    padding: 0.125rem 0.5rem;
    border-radius: 1rem;
    margin-left: auto;
  }

  .sidebar-divider {
    height: 1px;
    background: var(--border-subtle);
    margin: 0.5rem 0;
  }

  .categories-title {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--text-heading) !important;
    margin: 0.5rem 0;
    padding: 0 0.25rem;
  }

  .cat-item {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.375rem 1rem;
    background: none;
    border: none;
    font-size: 0.875rem;
    color: var(--text-secondary);
    cursor: pointer;
    font-family: inherit;
    width: 100%;
    text-align: left;
    border-radius: 0.25rem;
    transition: background 0.1s;
  }

  .cat-item:hover { background: rgba(var(--primary-rgb), 0.06); }

  .cat-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  /* ── Content area ── */
  .email-content {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    background: var(--bg-base);
  }

  .email-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 1.25rem;
    height: 3.5rem;
    border-bottom: 1px solid var(--border-subtle);
    background: var(--bg-card);
  }

  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .toolbar-checkbox {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
    display: flex;
  }

  .toolbar-tabs {
    display: flex;
    gap: 0;
  }

  .toolbar-tab {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1rem;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s;
    height: 3.5rem;
  }

  .toolbar-tab:hover { color: var(--primary); }

  .toolbar-tab--active {
    color: var(--primary) !important;
    border-bottom-color: var(--primary);
    font-weight: 600;
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .toolbar-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    background: none;
    border: none;
    border-radius: 0.375rem;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.1s;
  }

  .toolbar-icon:hover {
    background: rgba(var(--primary-rgb), 0.08);
    color: var(--primary);
  }

  .toolbar-separator {
    width: 1px;
    height: 1.5rem;
    background: var(--border-subtle);
    margin: 0 0.25rem;
  }

  .email-search {
    padding: 0.375rem 0.75rem;
    border: 1px solid var(--border-subtle);
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    font-family: inherit;
    background: var(--bg-input);
    color: var(--text-primary);
    width: 200px;
  }

  .email-search:focus { border-color: var(--primary); outline: none; }

  .toolbar-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.625rem;
    background: none;
    border: none;
    border-radius: 0.375rem;
    color: var(--text-secondary);
    cursor: pointer;
    font-family: inherit;
    font-size: 0.8125rem;
    transition: all 0.1s;
  }

  .toolbar-btn:hover { background: rgba(var(--primary-rgb), 0.08); color: var(--primary); }

  .email-loading, .email-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem;
    color: var(--text-muted);
  }

  /* ── Message list ── */
  .email-list {
    flex: 1;
    overflow-y: auto;
  }

  .msg-row {
    display: flex;
    align-items: center;
    padding: 0.375rem 1.25rem;
    min-height: 3.375rem;
    border-bottom: 1px solid var(--border-subtle);
    cursor: pointer;
    transition: background 0.1s;
    gap: 0.625rem;
    position: relative;
  }

  .msg-row:hover { background: rgba(var(--primary-rgb), 0.06); }

  /* Read messages — dimmed */
  .msg-row:not(.msg-row--unread) {
    opacity: 0.65;
  }
  .msg-row:not(.msg-row--unread):hover {
    opacity: 1;
  }

  /* Unread messages — bold + left accent */
  .msg-row--unread {
    opacity: 1;
    background: rgba(var(--primary-rgb), 0.04);
    border-left: 3px solid var(--primary);
  }

  .msg-row--selected { background: rgba(var(--primary-rgb), 0.08) !important; opacity: 1; }

  .msg-check, .msg-star {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
    flex-shrink: 0;
    display: flex;
  }

  .msg-sender {
    width: 160px;
    flex-shrink: 0;
    font-size: 0.875rem;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .msg-sender--bold { font-weight: 700 !important; color: var(--text-heading) !important; }

  .msg-content-col {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.1875rem;
    overflow: hidden;
  }

  .msg-content {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .msg-att-chips {
    display: flex;
    gap: 0.375rem;
    overflow: hidden;
  }

  .msg-att-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.125rem 0.5rem;
    border: 1px solid var(--border-subtle);
    border-radius: 1rem;
    font-size: 0.6875rem;
    color: var(--text-secondary) !important;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .msg-att-chip:hover {
    border-color: var(--primary);
    color: var(--primary) !important;
  }

  .msg-pj {
    flex-shrink: 0;
    display: flex;
    color: var(--text-muted);
    margin-right: 0.25rem;
  }

  .msg-subject {
    font-size: 0.8125rem;
    color: var(--text-heading);
  }

  .msg-subject--bold { font-weight: 600 !important; }

  .msg-snippet {
    font-size: 0.8125rem;
    color: var(--text-muted);
  }

  .msg-date {
    flex-shrink: 0;
    font-size: 0.75rem;
    color: var(--text-muted);
    text-align: right;
    min-width: 60px;
  }

  /* Hover actions (delete icon on hover) */
  .msg-hover-actions {
    position: absolute;
    right: 1rem;
    top: 50%;
    transform: translateY(-50%);
    display: none;
    gap: 0.25rem;
    background: var(--bg-card);
    padding: 0.25rem;
    border-radius: 0.25rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  }

  .msg-row:hover .msg-hover-actions { display: flex; }
  .msg-row:hover .msg-date { display: none; }

  .msg-hover-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.75rem;
    height: 1.75rem;
    background: none;
    border: none;
    border-radius: 0.25rem;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.1s;
  }

  .msg-hover-btn:hover { background: rgba(var(--primary-rgb), 0.1); color: var(--danger); }

  /* Loading spinner */
  @keyframes spin { to { transform: rotate(360deg); } }
  .spin { animation: spin 1s linear infinite; }

  .load-more-btn {
    width: 100%;
    padding: 0.75rem;
    background: none;
    border: none;
    border-top: 1px solid var(--border-subtle);
    color: var(--primary);
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
  }

  /* ── Compose ── */
  .compose-view {
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0;
    flex: 1;
  }

  .compose-field {
    border-bottom: 1px solid var(--border-subtle);
  }

  .compose-field input, .compose-field textarea {
    width: 100%;
    padding: 0.75rem 1rem;
    border: none;
    font-size: 0.9375rem;
    font-family: inherit;
    background: transparent;
    color: var(--text-primary);
    resize: vertical;
  }

  .compose-field input:focus, .compose-field textarea:focus { outline: none; }

  .compose-body { flex: 1; border-bottom: none; }
  .compose-body textarea { min-height: 200px; }

  .compose-actions {
    display: flex;
    gap: 0.75rem;
    padding-top: 1rem;
  }

  .discard-btn {
    background: rgba(255,94,94,0.1) !important;
    color: #FF5E5E !important;
    border: none !important;
  }

  .compose-send-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .compose-attachment-section {
    padding: 1rem 1rem 0;
  }

  .compose-attachment-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9375rem;
    font-weight: 500;
    color: var(--text-secondary) !important;
    margin: 0 0 0.5rem;
  }

  .compose-attachment-hint {
    font-size: 0.75rem;
    color: var(--text-muted) !important;
    margin: 0;
    font-style: italic;
  }

  /* ── Read view ── */
  .read-view {
    padding: 1.25rem;
    flex: 1;
    overflow-y: auto;
  }

  .read-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.5rem;
  }

  .read-actions {
    display: flex;
    gap: 0.25rem;
  }

  .read-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .read-avatar {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-weight: 700;
    font-size: 1rem;
    flex-shrink: 0;
  }

  .read-meta { flex: 1; }

  .read-from {
    font-size: 1rem;
    font-weight: 600;
    color: var(--primary) !important;
    margin: 0;
  }

  .read-email {
    font-size: 0.75rem;
    color: var(--text-muted) !important;
  }

  .read-date {
    font-size: 0.75rem;
    color: var(--text-muted) !important;
    flex-shrink: 0;
  }

  .read-subject {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-heading) !important;
    margin: 0 0 1rem;
  }

  .read-body {
    font-size: 0.875rem;
    line-height: 1.6;
    color: var(--text-primary);
    margin-bottom: 1.5rem;
    word-wrap: break-word;
    overflow-wrap: break-word;
  }

  .read-body :global(img) { max-width: 100%; height: auto; }
  .read-body :global(a) { color: var(--primary); }

  .read-body-text {
    white-space: pre-wrap;
    font-family: inherit;
    font-size: 0.875rem;
    margin: 0;
  }

  .read-attachments {
    padding: 1rem 0;
    border-top: 1px solid var(--border-subtle);
  }

  .read-attachments h5 {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-secondary) !important;
    margin: 0 0 0.5rem;
  }

  .att-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  /* Attachment card — Gmail style */
  .att-card {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border-subtle);
    border-radius: 0.5rem;
    background: var(--bg-card);
    min-width: 180px;
    transition: all 0.1s;
  }

  .att-card:hover {
    border-color: var(--primary);
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }

  .att-card__icon {
    flex-shrink: 0;
    display: flex;
  }

  .att-card__info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .att-card__name {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-heading) !important;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .att-card__size {
    font-size: 0.6875rem;
    color: var(--text-muted) !important;
  }

  .att-card__actions {
    display: flex;
    gap: 0.25rem;
    flex-shrink: 0;
  }

  .att-card__btn {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-muted);
    padding: 0.25rem;
    border-radius: 0.25rem;
    display: flex;
    transition: all 0.1s;
  }

  .att-card__btn:hover {
    color: var(--primary);
    background: rgba(var(--primary-rgb), 0.08);
  }

  /* Inline reply — YashAdmin style */
  .inline-reply {
    margin-top: 0.5rem;
  }

  .inline-reply-textarea {
    width: 100%;
    padding: 0.75rem 1rem;
    border: 1px solid var(--border-subtle);
    border-radius: 0.625rem;
    font-size: 0.875rem;
    font-family: inherit;
    background: var(--bg-input);
    color: var(--text-primary);
    resize: vertical;
    transition: border-color 0.15s;
  }

  .inline-reply-textarea:focus {
    border-color: var(--primary);
    outline: none;
  }

  .inline-reply-actions {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }

  .inline-reply-attach {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 0.375rem;
    cursor: pointer;
    color: var(--text-secondary);
    transition: all 0.1s;
    margin-right: auto;
  }

  .inline-reply-attach:hover {
    color: var(--primary);
    background: rgba(var(--primary-rgb), 0.08);
  }

  /* Compose file upload */
  .compose-file-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .compose-file-item {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.5rem;
    background: rgba(var(--primary-rgb), 0.08);
    border-radius: 0.25rem;
    font-size: 0.75rem;
  }

  .compose-file-name {
    color: var(--text-heading) !important;
    font-weight: 500;
  }

  .compose-file-size {
    color: var(--text-muted) !important;
  }

  .compose-file-remove {
    background: none;
    border: none;
    color: var(--danger);
    cursor: pointer;
    font-size: 1rem;
    padding: 0 0.25rem;
    line-height: 1;
  }

  .compose-file-drop {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 1rem;
    border: 1px dashed var(--border-subtle);
    border-radius: 0.625rem;
    cursor: pointer;
    color: var(--text-muted);
    font-size: 0.8125rem;
    transition: all 0.15s;
  }

  .compose-file-drop:hover {
    border-color: var(--primary);
    color: var(--primary);
    background: rgba(var(--primary-rgb), 0.03);
  }

  @media (max-width: 768px) {
    .email-page { flex-direction: column; }
    .email-sidebar { width: 100%; flex-direction: row; overflow-x: auto; }
    .email-folders { flex-direction: row; }
    .msg-sender { width: 100px; }
  }
</style>
