<script>
  import { onMount } from 'svelte';
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

  // Compose form
  let composeForm = { to: '', cc: '', subject: '', body: '' };
  let replyToId = null;
  let sending = false;

  // ── Folders ──
  const FOLDERS = [
    { key: 'inbox', label: 'Inbox', icon: 'mail' },
    { key: 'sent', label: 'Envoyes', icon: 'send' },
    { key: 'starred', label: 'Favoris', icon: 'star' },
    { key: 'draft', label: 'Brouillons', icon: 'file' },
    { key: 'important', label: 'Important', icon: 'tag' },
    { key: 'trash', label: 'Corbeille', icon: 'trash' },
  ];

  // ── Helpers ──
  function parseFromName(from) {
    if (!from) return 'Inconnu';
    const match = from.match(/^"?([^"<]+)"?\s*</);
    return match ? match[1].trim() : from.split('@')[0];
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

  async function fetchMessages(reset = true) {
    loading = true;
    try {
      const params = `folder=${currentFolder}&max_results=50${searchQuery ? `&q=${encodeURIComponent(searchQuery)}` : ''}`;
      const data = await api.get(`/api/gmail/messages?${params}`);
      messages = data.messages || [];
      nextPageToken = data.nextPageToken;
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
    } catch {}
    loadingMore = false;
  }

  async function fetchUnreadCount() {
    try {
      const { count } = await api.get('/api/gmail/unread-count');
      unreadCount = count;
    } catch { unreadCount = 0; }
  }

  async function openMessage(msg) {
    loading = true;
    try {
      selectedMessage = await api.get(`/api/gmail/messages/${msg.id}`);
      currentView = 'read';
      if (msg.unread) {
        await api.post(`/api/gmail/messages/${msg.id}/read`);
        msg.unread = false;
        messages = messages;
        fetchUnreadCount();
      }
    } catch (e) {
      console.error('Failed to open message', e);
    }
    loading = false;
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
      const payload = { ...composeForm };
      if (replyToId) payload.reply_to_message_id = replyToId;
      await api.post('/api/gmail/send', payload);
      composeForm = { to: '', cc: '', subject: '', body: '' };
      replyToId = null;
      currentView = 'inbox';
      await fetchMessages();
    } catch (e) {
      console.error('Failed to send', e);
    }
    sending = false;
  }

  function openCompose(replyMsg = null) {
    composeForm = { to: '', cc: '', subject: '', body: '' };
    replyToId = null;
    if (replyMsg) {
      composeForm.to = parseFromEmail(replyMsg.from);
      composeForm.subject = `Re: ${replyMsg.subject}`;
      replyToId = replyMsg.id;
    }
    currentView = 'compose';
  }

  function switchFolder(folder) {
    currentFolder = folder;
    currentView = 'inbox';
    selectedMessage = null;
    fetchMessages();
  }

  function backToInbox() {
    currentView = 'inbox';
    selectedMessage = null;
  }

  // ── Lifecycle ──
  onMount(async () => {
    await checkStatus();
    if (gmailConnected && hasScope) {
      await Promise.all([fetchMessages(), fetchUnreadCount()]);
    } else {
      loading = false;
    }
  });
</script>

<div class="email-page">
  <!-- ═══ Sidebar ═══ -->
  <div class="email-sidebar">
    <button class="compose-btn" on:click={() => openCompose()}>
      + Nouveau message
    </button>

    <div class="email-folders">
      {#each FOLDERS as f}
        <button
          class="folder-item"
          class:folder-item--active={currentFolder === f.key && currentView !== 'compose'}
          on:click={() => switchFolder(f.key)}
        >
          <span class="folder-label">{f.label}</span>
          {#if f.key === 'inbox' && unreadCount > 0}
            <span class="folder-badge">{unreadCount}</span>
          {/if}
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
      <!-- ── Inbox / Folder view ── -->
      <div class="email-toolbar">
        <div class="toolbar-left">
          <span class="toolbar-title">{FOLDERS.find(f => f.key === currentFolder)?.label || 'Inbox'}</span>
        </div>
        <div class="toolbar-right">
          <input
            type="text"
            class="email-search"
            placeholder="Rechercher..."
            bind:value={searchQuery}
            on:keydown={(e) => e.key === 'Enter' && fetchMessages()}
          />
          <button class="toolbar-btn" on:click={fetchMessages} title="Rafraichir">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 12a10 10 0 0118-6M22 12a10 10 0 01-18 6"/></svg>
          </button>
        </div>
      </div>

      {#if loading}
        <div class="email-loading">Chargement...</div>
      {:else if messages.length === 0}
        <div class="email-empty"><p>Aucun message</p></div>
      {:else}
        <div class="email-list">
          {#each messages as msg (msg.id)}
            <div
              class="msg-row"
              class:msg-row--unread={msg.unread}
              on:click={() => openMessage(msg)}
            >
              <button class="msg-star" on:click={(e) => toggleStar(msg, e)}>
                {#if msg.starred}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="#F8B940" stroke="#F8B940" stroke-width="1"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                {:else}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                {/if}
              </button>

              <div class="msg-sender" class:msg-sender--bold={msg.unread}>
                {parseFromName(msg.from)}
              </div>

              <div class="msg-content">
                <span class="msg-subject" class:msg-subject--bold={msg.unread}>{msg.subject}</span>
                <span class="msg-snippet">{msg.snippet}</span>
              </div>

              <div class="msg-date">{formatDate(msg.internalDate)}</div>
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
      <!-- ── Compose view ── -->
      <div class="compose-view">
        <div class="compose-field">
          <input type="text" placeholder="To:" bind:value={composeForm.to} />
        </div>
        <div class="compose-field">
          <input type="text" placeholder="Subject:" bind:value={composeForm.subject} />
        </div>
        <div class="compose-field compose-body">
          <textarea placeholder="Ecrivez votre message..." bind:value={composeForm.body} rows="12"></textarea>
        </div>
        <div class="compose-actions">
          <button class="ya-btn ya-btn--primary" on:click={sendEmail} disabled={sending || !composeForm.to || !composeForm.subject}>
            {sending ? 'Envoi...' : 'Envoyer'}
          </button>
          <button class="ya-btn discard-btn" on:click={backToInbox}>
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
            <h5>Pieces jointes ({selectedMessage.attachments.length})</h5>
            {#each selectedMessage.attachments as att}
              <span class="att-item">{att.filename} ({Math.round(att.size / 1024)}Ko)</span>
            {/each}
          </div>
        {/if}

        <div class="reply-area">
          <button class="ya-btn ya-btn--primary" on:click={() => openCompose(selectedMessage)}>
            Repondre
          </button>
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
    padding: 0.75rem;
    background: var(--primary);
    color: #fff;
    border: none;
    border-radius: 0.625rem;
    font-size: 0.9375rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    transition: filter 0.15s;
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
    justify-content: space-between;
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
  }

  .folder-item:hover {
    background: rgba(var(--primary-rgb), 0.08);
  }

  .folder-item--active {
    background: rgba(var(--primary-rgb), 0.12) !important;
    color: var(--primary) !important;
    font-weight: 600;
  }

  .folder-badge {
    background: var(--primary);
    color: #fff;
    font-size: 0.6875rem;
    font-weight: 600;
    padding: 0.125rem 0.5rem;
    border-radius: 1rem;
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
    padding: 0.75rem 1.25rem;
    border-bottom: 1px solid var(--border-subtle);
    background: var(--bg-card);
  }

  .toolbar-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-heading);
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
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
    padding: 0.625rem 1.25rem;
    border-bottom: 1px solid var(--border-subtle);
    cursor: pointer;
    transition: background 0.1s;
    gap: 0.75rem;
  }

  .msg-row:hover { background: rgba(var(--primary-rgb), 0.04); }
  .msg-row--unread { background: rgba(var(--primary-rgb), 0.03); }

  .msg-star {
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

  .msg-content {
    flex: 1;
    min-width: 0;
    display: flex;
    gap: 0.375rem;
    overflow: hidden;
  }

  .msg-subject {
    font-size: 0.8125rem;
    color: var(--text-heading);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .msg-subject--bold { font-weight: 600 !important; }

  .msg-snippet {
    font-size: 0.8125rem;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .msg-date {
    flex-shrink: 0;
    font-size: 0.75rem;
    color: var(--text-muted);
    text-align: right;
    min-width: 60px;
  }

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

  .att-item {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    background: rgba(var(--primary-rgb), 0.08);
    border-radius: 0.25rem;
    font-size: 0.75rem;
    color: var(--primary) !important;
    margin-right: 0.5rem;
    margin-bottom: 0.25rem;
  }

  .reply-area {
    padding-top: 1rem;
    border-top: 1px solid var(--border-subtle);
  }

  @media (max-width: 768px) {
    .email-page { flex-direction: column; }
    .email-sidebar { width: 100%; flex-direction: row; overflow-x: auto; }
    .email-folders { flex-direction: row; }
    .msg-sender { width: 100px; }
  }
</style>
