<script>
  import { onMount } from 'svelte';
  import { api } from '../api/client.js';
  import { currentUser } from '../stores/auth.js';
  import { Search, Send, Paperclip, MoreVertical, Phone, Video, Image, File } from 'lucide-svelte';

  let conversations = [];
  let activeConversation = null;
  let messages = [];
  let newMessage = '';
  let searchQuery = '';
  let loadingConvos = true;
  let loadingMessages = false;
  let sendingMessage = false;

  $: filteredConversations = searchQuery
    ? conversations.filter(c =>
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.last_message || '').toLowerCase().includes(searchQuery.toLowerCase())
      )
    : conversations;

  $: currentUserId = $currentUser?.id;

  onMount(async () => {
    try {
      conversations = await api.get('/api/chat/conversations');
    } catch (e) {
      conversations = getDemoConversations();
    } finally {
      loadingConvos = false;
    }
    if (conversations.length > 0) {
      selectConversation(conversations[0]);
    }
  });

  function getDemoConversations() {
    return [
      { id: 1, name: 'Sophie Martin', avatar: null, last_message: 'D\'accord, merci pour l\'info !', last_message_time: '10:32', unread_count: 2, online: true },
      { id: 2, name: 'Pierre Durand', avatar: null, last_message: 'Le serveur est redemarr\u00e9.', last_message_time: '09:15', unread_count: 0, online: true },
      { id: 3, name: 'Marie Lefebvre', avatar: null, last_message: 'Tu peux checker le ticket #234 ?', last_message_time: 'Hier', unread_count: 1, online: false },
      { id: 4, name: 'Lucas Bernard', avatar: null, last_message: 'Reunion a 14h confirm\u00e9e', last_message_time: 'Hier', unread_count: 0, online: false },
      { id: 5, name: 'Emma Petit', avatar: null, last_message: 'J\'ai push la correction', last_message_time: 'Lun', unread_count: 0, online: true },
    ];
  }

  function getDemoMessages(convId) {
    const msgs = {
      1: [
        { id: 1, sender_id: 99, text: 'Salut, tu as vu le ticket sur le VPN ?', timestamp: '2024-01-15T10:20:00', sender_name: 'Sophie Martin' },
        { id: 2, sender_id: currentUserId, text: 'Oui, je regarde ca maintenant', timestamp: '2024-01-15T10:25:00', sender_name: 'Moi' },
        { id: 3, sender_id: 99, text: 'Super, tiens moi au courant', timestamp: '2024-01-15T10:28:00', sender_name: 'Sophie Martin' },
        { id: 4, sender_id: currentUserId, text: 'C\'est bon, j\'ai identifie le probleme. C\'est le certificat qui a expire.', timestamp: '2024-01-15T10:30:00', sender_name: 'Moi' },
        { id: 5, sender_id: 99, text: 'D\'accord, merci pour l\'info !', timestamp: '2024-01-15T10:32:00', sender_name: 'Sophie Martin' },
      ],
    };
    return msgs[convId] || [
      { id: 1, sender_id: 99, text: 'Bonjour !', timestamp: '2024-01-15T09:00:00', sender_name: 'Contact' },
      { id: 2, sender_id: currentUserId, text: 'Salut, comment ca va ?', timestamp: '2024-01-15T09:05:00', sender_name: 'Moi' },
    ];
  }

  async function selectConversation(conv) {
    activeConversation = conv;
    conv.unread_count = 0;
    loadingMessages = true;
    try {
      messages = await api.get(`/api/chat/conversations/${conv.id}/messages`);
    } catch (e) {
      messages = getDemoMessages(conv.id);
    } finally {
      loadingMessages = false;
      scrollToBottom();
    }
  }

  async function sendMessage() {
    if (!newMessage.trim() || !activeConversation) return;
    const text = newMessage.trim();
    newMessage = '';
    sendingMessage = true;

    const optimistic = {
      id: Date.now(),
      sender_id: currentUserId,
      text,
      timestamp: new Date().toISOString(),
      sender_name: $currentUser?.display_name || 'Moi',
    };
    messages = [...messages, optimistic];
    scrollToBottom();

    try {
      await api.post(`/api/chat/conversations/${activeConversation.id}/messages`, { text });
      activeConversation.last_message = text;
      activeConversation.last_message_time = 'Now';
      conversations = conversations;
    } catch (e) {
      // keep optimistic message
    } finally {
      sendingMessage = false;
    }
  }

  function scrollToBottom() {
    setTimeout(() => {
      const el = document.querySelector('.chat-messages');
      if (el) el.scrollTop = el.scrollHeight;
    }, 50);
  }

  function getInitials(name) {
    return (name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  }

  function getAvatarColor(name) {
    const colors = ['#6941C6', '#e53e3e', '#38a169', '#d69e2e', '#3182ce', '#805ad5', '#dd6b20', '#319795'];
    let hash = 0;
    for (let i = 0; i < (name || '').length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
  }

  function formatTime(ts) {
    if (!ts) return '';
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    } catch { return ts; }
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }
</script>

<div class="chat-layout">
  <!-- Left: Contacts list -->
  <div class="chat-sidebar">
    <div class="sidebar-header">
      <h3>Messages</h3>
    </div>
    <div class="sidebar-search">
      <span class="search-icon"><Search size={16} /></span>
      <input type="text" placeholder="Rechercher..." bind:value={searchQuery} />
    </div>
    <div class="conversations-list">
      {#if loadingConvos}
        <div class="sidebar-loading">Chargement...</div>
      {:else if filteredConversations.length === 0}
        <div class="sidebar-empty">Aucune conversation</div>
      {:else}
        {#each filteredConversations as conv}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div
            class="conv-item"
            class:active={activeConversation?.id === conv.id}
            on:click={() => selectConversation(conv)}
          >
            <div class="conv-avatar" style="background:{getAvatarColor(conv.name)}">
              {getInitials(conv.name)}
              {#if conv.online}
                <span class="online-dot"></span>
              {/if}
            </div>
            <div class="conv-info">
              <div class="conv-top">
                <span class="conv-name">{conv.name}</span>
                <span class="conv-time">{conv.last_message_time || ''}</span>
              </div>
              <div class="conv-bottom">
                <span class="conv-preview">{conv.last_message || ''}</span>
                {#if conv.unread_count > 0}
                  <span class="unread-badge">{conv.unread_count}</span>
                {/if}
              </div>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>

  <!-- Center: Chat messages -->
  <div class="chat-main">
    {#if activeConversation}
      <div class="chat-header">
        <div class="chat-header-left">
          <div class="chat-header-avatar" style="background:{getAvatarColor(activeConversation.name)}">
            {getInitials(activeConversation.name)}
          </div>
          <div class="chat-header-info">
            <span class="chat-header-name">{activeConversation.name}</span>
            <span class="chat-header-status">
              {#if activeConversation.online}
                <span class="status-dot online"></span> En ligne
              {:else}
                <span class="status-dot offline"></span> Hors ligne
              {/if}
            </span>
          </div>
        </div>
        <div class="chat-header-actions">
          <button class="icon-btn"><Phone size={18} /></button>
          <button class="icon-btn"><Video size={18} /></button>
          <button class="icon-btn"><MoreVertical size={18} /></button>
        </div>
      </div>

      <div class="chat-messages">
        {#if loadingMessages}
          <div class="messages-loading">Chargement des messages...</div>
        {:else}
          {#each messages as msg}
            <div class="message-row" class:sent={msg.sender_id === currentUserId} class:received={msg.sender_id !== currentUserId}>
              <div class="message-bubble">
                <p class="message-text">{msg.text}</p>
                <span class="message-time">{formatTime(msg.timestamp)}</span>
              </div>
            </div>
          {/each}
        {/if}
      </div>

      <div class="chat-input-bar">
        <button class="icon-btn attach-btn"><Paperclip size={18} /></button>
        <input
          type="text"
          class="chat-input"
          placeholder="Tapez un message..."
          bind:value={newMessage}
          on:keydown={handleKeydown}
        />
        <button class="send-btn" on:click={sendMessage} disabled={!newMessage.trim() || sendingMessage}>
          <Send size={18} />
        </button>
      </div>
    {:else}
      <div class="chat-placeholder">
        <p>Selectionnez une conversation pour commencer</p>
      </div>
    {/if}
  </div>

  <!-- Right: Info panel -->
  <div class="chat-info-panel">
    {#if activeConversation}
      <div class="info-header">
        <div class="info-avatar" style="background:{getAvatarColor(activeConversation.name)}">
          {getInitials(activeConversation.name)}
        </div>
        <h4 class="info-name">{activeConversation.name}</h4>
        <p class="info-status">
          {#if activeConversation.online}En ligne{:else}Hors ligne{/if}
        </p>
      </div>

      <div class="info-section">
        <h5>Medias partages</h5>
        <div class="shared-media-grid">
          <div class="media-placeholder"><Image size={20} /></div>
          <div class="media-placeholder"><Image size={20} /></div>
          <div class="media-placeholder"><Image size={20} /></div>
          <div class="media-placeholder"><Image size={20} /></div>
          <div class="media-placeholder"><Image size={20} /></div>
          <div class="media-placeholder"><Image size={20} /></div>
        </div>
      </div>

      <div class="info-section">
        <h5>Fichiers partages</h5>
        <div class="shared-file">
          <span class="file-icon"><File size={16} /></span>
          <div class="file-info">
            <span class="file-name">rapport-serveur.pdf</span>
            <span class="file-size">2.4 MB</span>
          </div>
        </div>
        <div class="shared-file">
          <span class="file-icon"><File size={16} /></span>
          <div class="file-info">
            <span class="file-name">config-vpn.txt</span>
            <span class="file-size">12 KB</span>
          </div>
        </div>
      </div>
    {:else}
      <div class="info-empty">
        <p>Aucun contact selectionne</p>
      </div>
    {/if}
  </div>
</div>

<style>
  .chat-layout {
    display: flex;
    height: calc(100vh - 60px);
    background: var(--bg-base, #f5f5f9);
    font-family: 'Poppins', sans-serif;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border-subtle, #e4e6ef);
  }

  /* ── Sidebar ── */
  .chat-sidebar {
    width: 280px;
    min-width: 280px;
    background: var(--bg-card, #fff);
    border-right: 1px solid var(--border-subtle, #e4e6ef);
    display: flex;
    flex-direction: column;
  }

  .sidebar-header {
    padding: 1.25rem 1.25rem 0.75rem;
  }

  .sidebar-header h3 {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
  }

  .sidebar-search {
    padding: 0 1rem 0.75rem;
    position: relative;
  }

  .search-icon {
    position: absolute;
    left: 1.75rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted, #a2a5b9);
    display: flex;
    pointer-events: none;
  }

  .sidebar-search input {
    width: 100%;
    padding: 0.55rem 0.75rem 0.55rem 2.25rem;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 8px;
    font-size: 0.85rem;
    background: var(--bg-base, #f5f5f9);
    color: var(--text-heading, #1e1e2d);
    font-family: inherit;
  }

  .sidebar-search input:focus {
    outline: none;
    border-color: #6941C6;
  }

  .conversations-list {
    flex: 1;
    overflow-y: auto;
  }

  .sidebar-loading, .sidebar-empty {
    padding: 2rem;
    text-align: center;
    color: var(--text-muted, #a2a5b9);
    font-size: 0.85rem;
  }

  .conv-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1.25rem;
    cursor: pointer;
    transition: background 0.15s;
  }

  .conv-item:hover {
    background: var(--bg-base, #f5f5f9);
  }

  .conv-item.active {
    background: rgba(105, 65, 198, 0.08);
    border-left: 3px solid #6941C6;
  }

  .conv-avatar {
    width: 42px;
    height: 42px;
    min-width: 42px;
    border-radius: 50%;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
    font-weight: 700;
    position: relative;
  }

  .online-dot {
    position: absolute;
    bottom: 1px;
    right: 1px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #38a169;
    border: 2px solid var(--bg-card, #fff);
  }

  .conv-info {
    flex: 1;
    min-width: 0;
  }

  .conv-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .conv-name {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-heading, #1e1e2d);
  }

  .conv-time {
    font-size: 0.72rem;
    color: var(--text-muted, #a2a5b9);
  }

  .conv-bottom {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 2px;
  }

  .conv-preview {
    font-size: 0.8rem;
    color: var(--text-secondary, #6c7293);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
  }

  .unread-badge {
    background: #6941C6;
    color: #fff;
    font-size: 0.65rem;
    font-weight: 700;
    min-width: 18px;
    height: 18px;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 5px;
    margin-left: 8px;
  }

  /* ── Main chat area ── */
  .chat-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.85rem 1.25rem;
    background: var(--bg-card, #fff);
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
  }

  .chat-header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .chat-header-avatar {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
    font-weight: 700;
  }

  .chat-header-info {
    display: flex;
    flex-direction: column;
  }

  .chat-header-name {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-heading, #1e1e2d);
  }

  .chat-header-status {
    font-size: 0.75rem;
    color: var(--text-muted, #a2a5b9);
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
  }

  .status-dot.online { background: #38a169; }
  .status-dot.offline { background: #a2a5b9; }

  .chat-header-actions {
    display: flex;
    gap: 4px;
  }

  .icon-btn {
    width: 36px;
    height: 36px;
    border: none;
    background: transparent;
    color: var(--text-secondary, #6c7293);
    border-radius: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s;
  }

  .icon-btn:hover {
    background: var(--bg-base, #f5f5f9);
    color: #6941C6;
  }

  /* Messages */
  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .messages-loading {
    text-align: center;
    padding: 2rem;
    color: var(--text-muted, #a2a5b9);
  }

  .message-row {
    display: flex;
    max-width: 70%;
  }

  .message-row.sent {
    align-self: flex-end;
  }

  .message-row.received {
    align-self: flex-start;
  }

  .message-bubble {
    padding: 0.6rem 1rem;
    border-radius: 12px;
    position: relative;
  }

  .received .message-bubble {
    background: var(--bg-card, #fff);
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-bottom-left-radius: 4px;
  }

  .sent .message-bubble {
    background: linear-gradient(135deg, #452B90, #6941C6);
    color: #fff;
    border-bottom-right-radius: 4px;
  }

  .message-text {
    margin: 0;
    font-size: 0.88rem;
    line-height: 1.5;
  }

  .message-time {
    font-size: 0.65rem;
    opacity: 0.6;
    display: block;
    text-align: right;
    margin-top: 4px;
  }

  /* Input bar */
  .chat-input-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.85rem 1.25rem;
    background: var(--bg-card, #fff);
    border-top: 1px solid var(--border-subtle, #e4e6ef);
  }

  .attach-btn {
    color: var(--text-muted, #a2a5b9);
  }

  .chat-input {
    flex: 1;
    padding: 0.65rem 1rem;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 24px;
    font-size: 0.88rem;
    background: var(--bg-base, #f5f5f9);
    color: var(--text-heading, #1e1e2d);
    font-family: inherit;
  }

  .chat-input:focus {
    outline: none;
    border-color: #6941C6;
  }

  .send-btn {
    width: 40px;
    height: 40px;
    border: none;
    background: linear-gradient(135deg, #452B90, #6941C6);
    color: #fff;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.15s, box-shadow 0.15s;
    box-shadow: 0 2px 8px rgba(105, 65, 198, 0.3);
  }

  .send-btn:hover:not(:disabled) {
    transform: scale(1.05);
    box-shadow: 0 4px 14px rgba(105, 65, 198, 0.45);
  }

  .send-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .chat-placeholder {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted, #a2a5b9);
  }

  /* ── Info panel ── */
  .chat-info-panel {
    width: 280px;
    min-width: 280px;
    background: var(--bg-card, #fff);
    border-left: 1px solid var(--border-subtle, #e4e6ef);
    overflow-y: auto;
  }

  .info-header {
    text-align: center;
    padding: 2rem 1.25rem 1.25rem;
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
  }

  .info-avatar {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    font-weight: 700;
    margin: 0 auto 0.75rem;
  }

  .info-name {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
    margin: 0 0 0.25rem;
  }

  .info-status {
    font-size: 0.8rem;
    color: var(--text-muted, #a2a5b9);
    margin: 0;
  }

  .info-section {
    padding: 1.25rem;
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
  }

  .info-section h5 {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-secondary, #6c7293);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 0.75rem;
  }

  .shared-media-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
  }

  .media-placeholder {
    aspect-ratio: 1;
    border-radius: 8px;
    background: var(--bg-base, #f5f5f9);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted, #a2a5b9);
  }

  .shared-file {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.5rem 0;
  }

  .shared-file + .shared-file {
    border-top: 1px solid var(--border-subtle, #e4e6ef);
  }

  .file-icon {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: rgba(105, 65, 198, 0.08);
    color: #6941C6;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .file-info {
    display: flex;
    flex-direction: column;
  }

  .file-name {
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--text-heading, #1e1e2d);
  }

  .file-size {
    font-size: 0.72rem;
    color: var(--text-muted, #a2a5b9);
  }

  .info-empty {
    padding: 2rem;
    text-align: center;
    color: var(--text-muted, #a2a5b9);
    font-size: 0.85rem;
  }

  @media (max-width: 1024px) {
    .chat-info-panel { display: none; }
  }

  @media (max-width: 768px) {
    .chat-sidebar { width: 220px; min-width: 220px; }
  }
</style>
