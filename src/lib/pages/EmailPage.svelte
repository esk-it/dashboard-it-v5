<script>
  import { onMount } from 'svelte';
  import { api } from '../api/client.js';
  import { Inbox, Send, FileEdit, Trash2, Star, Reply, Forward, Paperclip, Plus, X, ChevronLeft, Search } from 'lucide-svelte';

  let folders = [
    { id: 'inbox', label: 'Boite de reception', icon: Inbox, count: 3 },
    { id: 'sent', label: 'Envoyes', icon: Send, count: 0 },
    { id: 'drafts', label: 'Brouillons', icon: FileEdit, count: 1 },
    { id: 'trash', label: 'Corbeille', icon: Trash2, count: 0 },
  ];

  let activeFolder = 'inbox';
  let emails = [];
  let selectedEmail = null;
  let loadingEmails = true;
  let searchQuery = '';

  // Compose state
  let showCompose = false;
  let composeTo = '';
  let composeCc = '';
  let composeSubject = '';
  let composeBody = '';
  let sending = false;

  $: filteredEmails = searchQuery
    ? emails.filter(e =>
        e.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
        e.from_name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : emails;

  onMount(() => {
    loadEmails(activeFolder);
  });

  async function loadEmails(folder) {
    activeFolder = folder;
    selectedEmail = null;
    loadingEmails = true;
    try {
      emails = await api.get(`/api/emails?folder=${folder}`);
    } catch (e) {
      emails = getDemoEmails(folder);
    } finally {
      loadingEmails = false;
    }
  }

  function getDemoEmails(folder) {
    if (folder === 'inbox') {
      return [
        { id: 1, from_name: 'Sophie Martin', from_email: 'sophie@company.com', subject: 'Mise a jour serveur production', preview: 'Bonjour, je voulais te prevenir que la mise a jour du serveur de production est prevue pour ce soir...', date: '2024-01-15T10:30:00', read: false, starred: false, body: 'Bonjour,\n\nJe voulais te prevenir que la mise a jour du serveur de production est prevue pour ce soir a 22h.\n\nMerci de confirmer ta disponibilite pour superviser l\'operation.\n\nCordialement,\nSophie Martin' },
        { id: 2, from_name: 'Pierre Durand', from_email: 'pierre@company.com', subject: 'Re: Ticket #1234 - VPN', preview: 'Le probleme a ete resolu. Le certificat a ete renouvele et le service VPN fonctionne a nouveau...', date: '2024-01-15T09:15:00', read: true, starred: true, body: 'Bonjour,\n\nLe probleme a ete resolu. Le certificat a ete renouvele et le service VPN fonctionne a nouveau correctement.\n\nMerci pour votre aide.\n\nPierre Durand' },
        { id: 3, from_name: 'Marie Lefebvre', from_email: 'marie@company.com', subject: 'Nouveau poste de travail', preview: 'Suite a notre reunion, je vous envoie la liste des logiciels a installer sur le nouveau poste...', date: '2024-01-14T16:45:00', read: false, starred: false, body: 'Bonjour,\n\nSuite a notre reunion, je vous envoie la liste des logiciels a installer sur le nouveau poste de travail:\n\n- Visual Studio Code\n- Docker Desktop\n- Git\n- Node.js\n\nMerci,\nMarie Lefebvre' },
        { id: 4, from_name: 'Lucas Bernard', from_email: 'lucas@company.com', subject: 'Reunion planning IT', preview: 'La reunion planning IT est confirmee pour jeudi a 14h en salle B2. Ordre du jour ci-joint...', date: '2024-01-14T14:20:00', read: true, starred: false, body: 'Bonjour a tous,\n\nLa reunion planning IT est confirmee pour jeudi a 14h en salle B2.\n\nOrdre du jour:\n1. Bilan du sprint\n2. Priorisation des tickets\n3. Planning de migration cloud\n\nCordialement,\nLucas Bernard' },
        { id: 5, from_name: 'Emma Petit', from_email: 'emma@company.com', subject: 'Alerte securite - Tentative intrusion', preview: 'Une tentative d\'intrusion a ete detectee sur le pare-feu a 03:42. Les logs ont ete analyses...', date: '2024-01-14T08:00:00', read: false, starred: true, body: 'URGENT\n\nUne tentative d\'intrusion a ete detectee sur le pare-feu a 03:42.\n\nLes logs ont ete analyses et l\'IP source a ete bloquee.\n\nMerci de verifier les regles de firewall.\n\nEmma Petit\nEquipe Securite' },
      ];
    }
    if (folder === 'sent') {
      return [
        { id: 10, from_name: 'Moi', from_email: 'me@company.com', subject: 'Re: Mise a jour serveur', preview: 'C\'est note, je serai disponible ce soir...', date: '2024-01-15T11:00:00', read: true, starred: false, body: 'C\'est note, je serai disponible ce soir pour superviser la mise a jour.\n\nCordialement' },
      ];
    }
    if (folder === 'drafts') {
      return [
        { id: 20, from_name: 'Moi', from_email: 'me@company.com', subject: 'Rapport mensuel IT', preview: 'Voici le rapport mensuel du departement IT...', date: '2024-01-15T08:00:00', read: true, starred: false, body: 'Voici le rapport mensuel du departement IT pour le mois de janvier...\n\n[Brouillon en cours]' },
      ];
    }
    return [];
  }

  async function selectEmail(email) {
    selectedEmail = email;
    if (!email.read) {
      email.read = true;
      emails = emails;
      const folder = folders.find(f => f.id === activeFolder);
      if (folder && folder.count > 0) folder.count--;
      folders = folders;
    }
    // Try to fetch full email
    try {
      const full = await api.get(`/api/emails/${email.id}`);
      selectedEmail = { ...email, ...full };
    } catch (e) {
      // keep current data
    }
  }

  function toggleStar(e, email) {
    e.stopPropagation();
    email.starred = !email.starred;
    emails = emails;
  }

  async function sendEmail() {
    if (!composeTo.trim() || !composeSubject.trim()) return;
    sending = true;
    try {
      await api.post('/api/emails', {
        to: composeTo,
        cc: composeCc,
        subject: composeSubject,
        body: composeBody,
      });
    } catch (e) {
      // silently close
    } finally {
      sending = false;
      showCompose = false;
      composeTo = '';
      composeCc = '';
      composeSubject = '';
      composeBody = '';
    }
  }

  function formatDate(ts) {
    if (!ts) return '';
    try {
      const d = new Date(ts);
      const now = new Date();
      if (d.toDateString() === now.toDateString()) {
        return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
      }
      return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
    } catch { return ts; }
  }

  function formatFullDate(ts) {
    if (!ts) return '';
    try {
      return new Date(ts).toLocaleDateString('fr-FR', {
        weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch { return ts; }
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
</script>

<div class="email-layout">
  <!-- Left: Folder nav -->
  <div class="email-sidebar">
    <button class="compose-btn" on:click={() => showCompose = true}>
      <Plus size={18} />
      Composer
    </button>

    <nav class="folder-list">
      {#each folders as folder}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          class="folder-item"
          class:active={activeFolder === folder.id}
          on:click={() => loadEmails(folder.id)}
        >
          <span class="folder-icon"><svelte:component this={folder.icon} size={18} /></span>
          <span class="folder-label">{folder.label}</span>
          {#if folder.count > 0}
            <span class="folder-count">{folder.count}</span>
          {/if}
        </div>
      {/each}
    </nav>
  </div>

  <!-- Center: Email list -->
  <div class="email-list-panel">
    <div class="list-header">
      <h3>{folders.find(f => f.id === activeFolder)?.label || 'Emails'}</h3>
      <div class="list-search">
        <span class="list-search-icon"><Search size={15} /></span>
        <input type="text" placeholder="Rechercher..." bind:value={searchQuery} />
      </div>
    </div>

    <div class="email-list">
      {#if loadingEmails}
        <div class="list-loading">Chargement...</div>
      {:else if filteredEmails.length === 0}
        <div class="list-empty">Aucun email</div>
      {:else}
        {#each filteredEmails as email}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div
            class="email-item"
            class:active={selectedEmail?.id === email.id}
            class:unread={!email.read}
            on:click={() => selectEmail(email)}
          >
            <div class="email-item-avatar" style="background:{getAvatarColor(email.from_name)}">
              {getInitials(email.from_name)}
            </div>
            <div class="email-item-content">
              <div class="email-item-top">
                <span class="email-item-sender">{email.from_name}</span>
                <span class="email-item-date">{formatDate(email.date)}</span>
              </div>
              <div class="email-item-subject">{email.subject}</div>
              <div class="email-item-preview">{email.preview || ''}</div>
            </div>
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <span class="star-btn" class:starred={email.starred} on:click={(e) => toggleStar(e, email)}>
              <Star size={16} />
            </span>
          </div>
        {/each}
      {/if}
    </div>
  </div>

  <!-- Right: Email detail -->
  <div class="email-detail-panel">
    {#if selectedEmail}
      <div class="detail-header">
        <h2 class="detail-subject">{selectedEmail.subject}</h2>
        <div class="detail-actions">
          <button class="detail-action-btn" title="Repondre">
            <Reply size={16} />
            Repondre
          </button>
          <button class="detail-action-btn" title="Transferer">
            <Forward size={16} />
            Transferer
          </button>
          <button class="detail-action-btn danger" title="Supprimer">
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      <div class="detail-meta">
        <div class="detail-avatar" style="background:{getAvatarColor(selectedEmail.from_name)}">
          {getInitials(selectedEmail.from_name)}
        </div>
        <div class="detail-meta-info">
          <span class="detail-from">{selectedEmail.from_name}</span>
          <span class="detail-email">&lt;{selectedEmail.from_email}&gt;</span>
          <span class="detail-date">{formatFullDate(selectedEmail.date)}</span>
        </div>
      </div>

      <div class="detail-body">
        <pre class="email-body-text">{selectedEmail.body || selectedEmail.preview || ''}</pre>
      </div>
    {:else}
      <div class="detail-empty">
        <Inbox size={48} />
        <p>Selectionnez un email pour le lire</p>
      </div>
    {/if}
  </div>
</div>

<!-- Compose modal -->
{#if showCompose}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="compose-overlay" on:click={() => showCompose = false}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="compose-modal" on:click|stopPropagation>
      <div class="compose-header">
        <h3>Nouveau message</h3>
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span class="compose-close" on:click={() => showCompose = false}><X size={18} /></span>
      </div>

      <div class="compose-body">
        <div class="compose-field">
          <label>A</label>
          <input type="text" bind:value={composeTo} placeholder="destinataire@email.com" />
        </div>
        <div class="compose-field">
          <label>Cc</label>
          <input type="text" bind:value={composeCc} placeholder="copie@email.com" />
        </div>
        <div class="compose-field">
          <label>Objet</label>
          <input type="text" bind:value={composeSubject} placeholder="Objet du message" />
        </div>
        <textarea
          class="compose-textarea"
          bind:value={composeBody}
          placeholder="Redigez votre message..."
          rows="10"
        ></textarea>
      </div>

      <div class="compose-footer">
        <button class="compose-send-btn" on:click={sendEmail} disabled={sending || !composeTo.trim()}>
          <Send size={16} />
          {#if sending}Envoi...{:else}Envoyer{/if}
        </button>
        <button class="compose-attach-btn">
          <Paperclip size={16} />
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .email-layout {
    display: flex;
    height: calc(100vh - 60px);
    background: var(--bg-base, #f5f5f9);
    font-family: 'Poppins', sans-serif;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border-subtle, #e4e6ef);
  }

  /* ── Sidebar ── */
  .email-sidebar {
    width: 220px;
    min-width: 220px;
    background: var(--bg-card, #fff);
    border-right: 1px solid var(--border-subtle, #e4e6ef);
    padding: 1.25rem 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .compose-btn {
    width: 100%;
    padding: 0.7rem 1rem;
    background: linear-gradient(135deg, #452B90, #6941C6);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(105, 65, 198, 0.3);
  }

  .compose-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(105, 65, 198, 0.45);
  }

  .folder-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .folder-item {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.6rem 0.85rem;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.85rem;
    color: var(--text-secondary, #6c7293);
    transition: all 0.15s;
  }

  .folder-item:hover {
    background: var(--bg-base, #f5f5f9);
    color: var(--text-heading, #1e1e2d);
  }

  .folder-item.active {
    background: rgba(105, 65, 198, 0.08);
    color: #6941C6;
    font-weight: 600;
  }

  .folder-icon {
    display: flex;
    align-items: center;
  }

  .folder-label {
    flex: 1;
  }

  .folder-count {
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
  }

  /* ── Email list ── */
  .email-list-panel {
    width: 360px;
    min-width: 300px;
    background: var(--bg-card, #fff);
    border-right: 1px solid var(--border-subtle, #e4e6ef);
    display: flex;
    flex-direction: column;
  }

  .list-header {
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
  }

  .list-header h3 {
    margin: 0 0 0.6rem;
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
  }

  .list-search {
    position: relative;
  }

  .list-search-icon {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted, #a2a5b9);
    display: flex;
    pointer-events: none;
  }

  .list-search input {
    width: 100%;
    padding: 0.5rem 0.75rem 0.5rem 2rem;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 8px;
    font-size: 0.82rem;
    background: var(--bg-base, #f5f5f9);
    color: var(--text-heading, #1e1e2d);
    font-family: inherit;
  }

  .list-search input:focus {
    outline: none;
    border-color: #6941C6;
  }

  .email-list {
    flex: 1;
    overflow-y: auto;
  }

  .list-loading, .list-empty {
    padding: 2rem;
    text-align: center;
    color: var(--text-muted, #a2a5b9);
    font-size: 0.85rem;
  }

  .email-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.85rem 1.25rem;
    cursor: pointer;
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
    transition: background 0.15s;
    position: relative;
  }

  .email-item:hover {
    background: var(--bg-base, #f5f5f9);
  }

  .email-item.active {
    background: rgba(105, 65, 198, 0.06);
    border-left: 3px solid #6941C6;
  }

  .email-item.unread {
    background: rgba(105, 65, 198, 0.03);
  }

  .email-item.unread .email-item-sender,
  .email-item.unread .email-item-subject {
    font-weight: 700;
  }

  .email-item-avatar {
    width: 36px;
    height: 36px;
    min-width: 36px;
    border-radius: 50%;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.72rem;
    font-weight: 700;
    margin-top: 2px;
  }

  .email-item-content {
    flex: 1;
    min-width: 0;
  }

  .email-item-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .email-item-sender {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-heading, #1e1e2d);
  }

  .email-item-date {
    font-size: 0.7rem;
    color: var(--text-muted, #a2a5b9);
    white-space: nowrap;
  }

  .email-item-subject {
    font-size: 0.82rem;
    color: var(--text-heading, #1e1e2d);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .email-item-preview {
    font-size: 0.78rem;
    color: var(--text-muted, #a2a5b9);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .star-btn {
    color: var(--text-muted, #a2a5b9);
    cursor: pointer;
    display: flex;
    align-items: center;
    margin-top: 4px;
    transition: color 0.15s;
  }

  .star-btn:hover { color: #d69e2e; }
  .star-btn.starred { color: #d69e2e; }

  /* ── Detail panel ── */
  .email-detail-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    background: var(--bg-card, #fff);
  }

  .detail-header {
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .detail-subject {
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
    margin: 0;
    flex: 1;
  }

  .detail-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .detail-action-btn {
    padding: 0.4rem 0.75rem;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 6px;
    background: var(--bg-card, #fff);
    color: var(--text-secondary, #6c7293);
    font-size: 0.78rem;
    font-family: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: all 0.15s;
  }

  .detail-action-btn:hover {
    background: var(--bg-base, #f5f5f9);
    color: #6941C6;
    border-color: #6941C6;
  }

  .detail-action-btn.danger:hover {
    color: #e53e3e;
    border-color: #e53e3e;
  }

  .detail-meta {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
  }

  .detail-avatar {
    width: 42px;
    height: 42px;
    border-radius: 50%;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.85rem;
    font-weight: 700;
  }

  .detail-meta-info {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .detail-from {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-heading, #1e1e2d);
  }

  .detail-email {
    font-size: 0.78rem;
    color: var(--text-muted, #a2a5b9);
  }

  .detail-date {
    font-size: 0.75rem;
    color: var(--text-muted, #a2a5b9);
  }

  .detail-body {
    flex: 1;
    padding: 1.5rem;
  }

  .email-body-text {
    font-family: 'Poppins', sans-serif;
    font-size: 0.9rem;
    line-height: 1.7;
    color: var(--text-heading, #1e1e2d);
    white-space: pre-wrap;
    margin: 0;
  }

  .detail-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--text-muted, #a2a5b9);
    gap: 1rem;
  }

  .detail-empty p {
    margin: 0;
    font-size: 0.9rem;
  }

  /* ── Compose modal ── */
  .compose-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(2px);
  }

  .compose-modal {
    width: 600px;
    max-width: 95vw;
    max-height: 85vh;
    background: var(--bg-card, #fff);
    border-radius: 12px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .compose-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
    background: linear-gradient(135deg, #452B90, #6941C6);
    color: #fff;
  }

  .compose-header h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
  }

  .compose-close {
    cursor: pointer;
    display: flex;
    opacity: 0.8;
  }

  .compose-close:hover { opacity: 1; }

  .compose-body {
    padding: 1rem 1.25rem;
    flex: 1;
    overflow-y: auto;
  }

  .compose-field {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0;
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
  }

  .compose-field label {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-secondary, #6c7293);
    min-width: 40px;
  }

  .compose-field input {
    flex: 1;
    border: none;
    padding: 0.4rem 0;
    font-size: 0.88rem;
    background: transparent;
    color: var(--text-heading, #1e1e2d);
    font-family: inherit;
  }

  .compose-field input:focus { outline: none; }

  .compose-textarea {
    width: 100%;
    border: none;
    padding: 0.75rem 0;
    font-size: 0.88rem;
    font-family: inherit;
    color: var(--text-heading, #1e1e2d);
    background: transparent;
    resize: none;
    line-height: 1.6;
  }

  .compose-textarea:focus { outline: none; }

  .compose-footer {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.25rem;
    border-top: 1px solid var(--border-subtle, #e4e6ef);
  }

  .compose-send-btn {
    padding: 0.55rem 1.25rem;
    background: linear-gradient(135deg, #452B90, #6941C6);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    transition: all 0.2s;
  }

  .compose-send-btn:hover:not(:disabled) {
    box-shadow: 0 4px 14px rgba(105, 65, 198, 0.4);
  }

  .compose-send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  .compose-attach-btn {
    width: 36px;
    height: 36px;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 8px;
    background: transparent;
    color: var(--text-secondary, #6c7293);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .compose-attach-btn:hover {
    color: #6941C6;
    border-color: #6941C6;
  }

  @media (max-width: 1024px) {
    .email-list-panel { width: 280px; min-width: 240px; }
  }

  @media (max-width: 768px) {
    .email-sidebar { width: 180px; min-width: 180px; }
    .email-list-panel { display: none; }
  }
</style>
