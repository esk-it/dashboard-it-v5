<script>
  import { onMount } from 'svelte';
  import { api } from '../api/client.js';
  import { Users2, Grid, List, Plus, Edit, Trash2, Search, MoreVertical, X, Shield, User, UserCheck, Activity } from 'lucide-svelte';

  let users = [];
  let loading = true;
  let viewMode = 'grid'; // 'grid' | 'list'
  let searchQuery = '';

  // Modal state
  let showModal = false;
  let editingUser = null;
  let formName = '';
  let formUsername = '';
  let formEmail = '';
  let formRole = 'user';
  let formPassword = '';
  let saving = false;
  let formError = '';

  // Stats
  $: totalUsers = users.length;
  $: activeUsers = users.filter(u => u.is_active !== false).length;
  $: adminCount = users.filter(u => u.role === 'admin').length;
  $: userCount = users.filter(u => u.role !== 'admin').length;

  $: filteredUsers = searchQuery
    ? users.filter(u =>
        (u.display_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (u.username || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (u.email || '').toLowerCase().includes(searchQuery.toLowerCase())
      )
    : users;

  onMount(async () => {
    await loadUsers();
  });

  async function loadUsers() {
    loading = true;
    try {
      users = await api.get('/api/users');
    } catch (e) {
      users = getDemoUsers();
    } finally {
      loading = false;
    }
  }

  function getDemoUsers() {
    return [
      { id: 1, display_name: 'Admin Principal', username: 'admin', email: 'admin@company.com', role: 'admin', is_active: true, last_login: '2024-01-15T10:30:00' },
      { id: 2, display_name: 'Sophie Martin', username: 'smartin', email: 'sophie@company.com', role: 'user', is_active: true, last_login: '2024-01-15T09:15:00' },
      { id: 3, display_name: 'Pierre Durand', username: 'pdurand', email: 'pierre@company.com', role: 'user', is_active: true, last_login: '2024-01-14T16:45:00' },
      { id: 4, display_name: 'Marie Lefebvre', username: 'mlefebvre', email: 'marie@company.com', role: 'admin', is_active: true, last_login: '2024-01-14T14:20:00' },
      { id: 5, display_name: 'Lucas Bernard', username: 'lbernard', email: 'lucas@company.com', role: 'user', is_active: false, last_login: '2024-01-10T08:00:00' },
      { id: 6, display_name: 'Emma Petit', username: 'epetit', email: 'emma@company.com', role: 'user', is_active: true, last_login: '2024-01-15T11:00:00' },
    ];
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

  function formatDate(ts) {
    if (!ts) return 'Jamais';
    try {
      const d = new Date(ts);
      return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return ts; }
  }

  function openAddModal() {
    editingUser = null;
    formName = '';
    formUsername = '';
    formEmail = '';
    formRole = 'user';
    formPassword = '';
    formError = '';
    showModal = true;
  }

  function openEditModal(user) {
    editingUser = user;
    formName = user.display_name || '';
    formUsername = user.username || '';
    formEmail = user.email || '';
    formRole = user.role || 'user';
    formPassword = '';
    formError = '';
    showModal = true;
  }

  async function saveUser() {
    if (!formUsername.trim() || !formEmail.trim()) {
      formError = 'Identifiant et email sont requis';
      return;
    }
    if (!editingUser && !formPassword.trim()) {
      formError = 'Le mot de passe est requis pour un nouvel utilisateur';
      return;
    }

    saving = true;
    formError = '';

    const payload = {
      display_name: formName,
      username: formUsername,
      email: formEmail,
      role: formRole,
    };
    if (formPassword) payload.password = formPassword;

    try {
      if (editingUser) {
        await api.put(`/api/users/${editingUser.id}`, payload);
        // Update local
        const idx = users.findIndex(u => u.id === editingUser.id);
        if (idx >= 0) {
          users[idx] = { ...users[idx], ...payload };
          users = users;
        }
      } else {
        const created = await api.post('/api/users', payload);
        users = [...users, created || { ...payload, id: Date.now(), is_active: true, last_login: null }];
      }
      showModal = false;
    } catch (e) {
      formError = e.message || 'Erreur lors de la sauvegarde';
    } finally {
      saving = false;
    }
  }

  async function deleteUser(user) {
    if (!confirm(`Supprimer l'utilisateur ${user.display_name || user.username} ?`)) return;
    try {
      await api.delete(`/api/users/${user.id}`);
    } catch (e) {
      // continue locally
    }
    users = users.filter(u => u.id !== user.id);
  }
</script>

<div class="user-manager">
  <!-- Stats row -->
  <div class="stats-row">
    <div class="stat-card" style="--accent: #6941C6">
      <div class="stat-icon"><Users2 size={22} /></div>
      <div class="stat-info">
        <span class="stat-value">{totalUsers}</span>
        <span class="stat-label">Total utilisateurs</span>
      </div>
    </div>
    <div class="stat-card" style="--accent: #38a169">
      <div class="stat-icon"><Activity size={22} /></div>
      <div class="stat-info">
        <span class="stat-value">{activeUsers}</span>
        <span class="stat-label">Actifs</span>
      </div>
    </div>
    <div class="stat-card" style="--accent: #e53e3e">
      <div class="stat-icon"><Shield size={22} /></div>
      <div class="stat-info">
        <span class="stat-value">{adminCount}</span>
        <span class="stat-label">Admins</span>
      </div>
    </div>
    <div class="stat-card" style="--accent: #3182ce">
      <div class="stat-icon"><UserCheck size={22} /></div>
      <div class="stat-info">
        <span class="stat-value">{userCount}</span>
        <span class="stat-label">Utilisateurs</span>
      </div>
    </div>
  </div>

  <!-- Header -->
  <div class="manager-header">
    <div class="header-left">
      <h2>Gestion des utilisateurs</h2>
    </div>
    <div class="header-right">
      <div class="header-search">
        <span class="search-icon"><Search size={16} /></span>
        <input type="text" placeholder="Rechercher..." bind:value={searchQuery} />
      </div>
      <div class="view-toggle">
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span class="toggle-btn" class:active={viewMode === 'grid'} on:click={() => viewMode = 'grid'}>
          <Grid size={18} />
        </span>
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span class="toggle-btn" class:active={viewMode === 'list'} on:click={() => viewMode = 'list'}>
          <List size={18} />
        </span>
      </div>
      <button class="add-btn" on:click={openAddModal}>
        <Plus size={18} />
        Ajouter
      </button>
    </div>
  </div>

  <!-- Content -->
  {#if loading}
    <div class="loading-state">Chargement des utilisateurs...</div>
  {:else if filteredUsers.length === 0}
    <div class="empty-state">Aucun utilisateur trouve</div>
  {:else if viewMode === 'grid'}
    <div class="user-grid">
      {#each filteredUsers as user}
        <div class="user-card">
          <div class="card-header">
            <div class="card-avatar" style="background:{getAvatarColor(user.display_name || user.username)}">
              {getInitials(user.display_name || user.username)}
            </div>
            <div class="card-actions">
              <button class="card-action-btn" on:click={() => openEditModal(user)} title="Modifier">
                <Edit size={14} />
              </button>
              <button class="card-action-btn danger" on:click={() => deleteUser(user)} title="Supprimer">
                <Trash2 size={14} />
              </button>
            </div>
          </div>
          <h4 class="card-name">{user.display_name || user.username}</h4>
          <p class="card-email">{user.email || ''}</p>
          <div class="card-meta">
            <span class="role-badge" class:admin={user.role === 'admin'}>
              {user.role === 'admin' ? 'Admin' : 'Utilisateur'}
            </span>
            <span class="status-badge" class:active={user.is_active !== false} class:inactive={user.is_active === false}>
              {user.is_active !== false ? 'Actif' : 'Inactif'}
            </span>
          </div>
          <p class="card-last-login">Dernier acces: {formatDate(user.last_login)}</p>
        </div>
      {/each}
    </div>
  {:else}
    <div class="user-table-wrap">
      <table class="ya-table">
        <thead>
          <tr>
            <th>Utilisateur</th>
            <th>Role</th>
            <th>Statut</th>
            <th>Dernier acces</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredUsers as user}
            <tr>
              <td>
                <div class="table-user">
                  <div class="table-avatar" style="background:{getAvatarColor(user.display_name || user.username)}">
                    {getInitials(user.display_name || user.username)}
                  </div>
                  <div class="table-user-info">
                    <span class="table-user-name">{user.display_name || user.username}</span>
                    <span class="table-user-email">{user.email || ''}</span>
                  </div>
                </div>
              </td>
              <td>
                <span class="role-badge" class:admin={user.role === 'admin'}>
                  {user.role === 'admin' ? 'Admin' : 'Utilisateur'}
                </span>
              </td>
              <td>
                <span class="status-badge" class:active={user.is_active !== false} class:inactive={user.is_active === false}>
                  {user.is_active !== false ? 'Actif' : 'Inactif'}
                </span>
              </td>
              <td class="date-cell">{formatDate(user.last_login)}</td>
              <td>
                <div class="table-actions">
                  <button class="table-action-btn" on:click={() => openEditModal(user)} title="Modifier">
                    <Edit size={14} />
                  </button>
                  <button class="table-action-btn danger" on:click={() => deleteUser(user)} title="Supprimer">
                    <Trash2 size={14} />
                  </button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- Add/Edit modal -->
{#if showModal}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-overlay" on:click={() => showModal = false}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-card" on:click|stopPropagation>
      <div class="modal-header">
        <h3>{editingUser ? 'Modifier l\'utilisateur' : 'Nouvel utilisateur'}</h3>
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span class="modal-close" on:click={() => showModal = false}><X size={18} /></span>
      </div>

      <div class="modal-body">
        {#if formError}
          <div class="modal-error">{formError}</div>
        {/if}

        <div class="modal-field">
          <label for="m-name">Nom complet</label>
          <input id="m-name" type="text" bind:value={formName} placeholder="Jean Dupont" />
        </div>

        <div class="modal-row">
          <div class="modal-field">
            <label for="m-username">Identifiant</label>
            <input id="m-username" type="text" bind:value={formUsername} placeholder="jdupont" required />
          </div>
          <div class="modal-field">
            <label for="m-role">Role</label>
            <select id="m-role" bind:value={formRole}>
              <option value="user">Utilisateur</option>
              <option value="admin">Administrateur</option>
            </select>
          </div>
        </div>

        <div class="modal-field">
          <label for="m-email">Email</label>
          <input id="m-email" type="email" bind:value={formEmail} placeholder="jean@company.com" required />
        </div>

        <div class="modal-field">
          <label for="m-password">
            Mot de passe
            {#if editingUser}<span class="field-hint">(laisser vide pour ne pas changer)</span>{/if}
          </label>
          <input id="m-password" type="password" bind:value={formPassword} placeholder="Mot de passe" />
        </div>
      </div>

      <div class="modal-footer">
        <button class="modal-cancel" on:click={() => showModal = false}>Annuler</button>
        <button class="modal-save" on:click={saveUser} disabled={saving}>
          {#if saving}Enregistrement...{:else}{editingUser ? 'Modifier' : 'Creer'}{/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .user-manager {
    font-family: 'Poppins', sans-serif;
    animation: fadeIn 0.3s ease-out;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  /* ── Stats row ── */
  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .stat-card {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.25rem;
    background: var(--bg-card, #fff);
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  }

  .stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--accent) 10%, transparent);
    color: var(--accent);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .stat-info {
    display: flex;
    flex-direction: column;
  }

  .stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
    line-height: 1;
  }

  .stat-label {
    font-size: 0.78rem;
    color: var(--text-muted, #a2a5b9);
    margin-top: 2px;
  }

  /* ── Header ── */
  .manager-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.25rem;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .manager-header h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .header-search {
    position: relative;
  }

  .search-icon {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted, #a2a5b9);
    display: flex;
    pointer-events: none;
  }

  .header-search input {
    padding: 0.55rem 0.75rem 0.55rem 2.25rem;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 8px;
    font-size: 0.85rem;
    background: var(--bg-card, #fff);
    color: var(--text-heading, #1e1e2d);
    font-family: inherit;
    width: 220px;
  }

  .header-search input:focus {
    outline: none;
    border-color: #6941C6;
  }

  .view-toggle {
    display: flex;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 8px;
    overflow: hidden;
  }

  .toggle-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--text-muted, #a2a5b9);
    transition: all 0.15s;
    background: var(--bg-card, #fff);
  }

  .toggle-btn:hover { color: #6941C6; }

  .toggle-btn.active {
    background: #6941C6;
    color: #fff;
  }

  .add-btn {
    padding: 0.55rem 1rem;
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
    box-shadow: 0 2px 8px rgba(105, 65, 198, 0.3);
  }

  .add-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(105, 65, 198, 0.45);
  }

  /* ── Loading / Empty ── */
  .loading-state, .empty-state {
    padding: 3rem;
    text-align: center;
    color: var(--text-muted, #a2a5b9);
    font-size: 0.9rem;
    background: var(--bg-card, #fff);
    border-radius: 12px;
    border: 1px solid var(--border-subtle, #e4e6ef);
  }

  /* ── Grid view ── */
  .user-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
  }

  .user-card {
    background: var(--bg-card, #fff);
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    transition: box-shadow 0.2s, transform 0.2s;
  }

  .user-card:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
    transform: translateY(-2px);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1rem;
  }

  .card-avatar {
    width: 52px;
    height: 52px;
    border-radius: 50%;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1rem;
    font-weight: 700;
  }

  .card-actions {
    display: flex;
    gap: 4px;
  }

  .card-action-btn {
    width: 30px;
    height: 30px;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted, #a2a5b9);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
  }

  .card-action-btn:hover {
    color: #6941C6;
    border-color: #6941C6;
    background: rgba(105, 65, 198, 0.05);
  }

  .card-action-btn.danger:hover {
    color: #e53e3e;
    border-color: #e53e3e;
    background: rgba(229, 62, 62, 0.05);
  }

  .card-name {
    margin: 0 0 0.2rem;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-heading, #1e1e2d);
  }

  .card-email {
    margin: 0 0 0.75rem;
    font-size: 0.82rem;
    color: var(--text-muted, #a2a5b9);
  }

  .card-meta {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .role-badge {
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    background: rgba(49, 130, 206, 0.1);
    color: #3182ce;
  }

  .role-badge.admin {
    background: rgba(229, 62, 62, 0.1);
    color: #e53e3e;
  }

  .status-badge {
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
  }

  .status-badge.active {
    background: rgba(56, 161, 105, 0.1);
    color: #38a169;
  }

  .status-badge.inactive {
    background: rgba(160, 160, 160, 0.1);
    color: #a0a0a0;
  }

  .card-last-login {
    margin: 0;
    font-size: 0.75rem;
    color: var(--text-muted, #a2a5b9);
  }

  /* ── Table view ── */
  .user-table-wrap {
    background: var(--bg-card, #fff);
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 12px;
    overflow: hidden;
  }

  .ya-table {
    width: 100%;
    border-collapse: collapse;
  }

  .ya-table thead th {
    text-align: left;
    padding: 0.85rem 1rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-secondary, #6c7293);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    background: var(--bg-base, #f5f5f9);
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
  }

  .ya-table tbody tr {
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
    transition: background 0.15s;
  }

  .ya-table tbody tr:hover {
    background: rgba(105, 65, 198, 0.02);
  }

  .ya-table tbody tr:last-child {
    border-bottom: none;
  }

  .ya-table td {
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: var(--text-heading, #1e1e2d);
    vertical-align: middle;
  }

  .table-user {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .table-avatar {
    width: 36px;
    height: 36px;
    min-width: 36px;
    border-radius: 50%;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
  }

  .table-user-info {
    display: flex;
    flex-direction: column;
  }

  .table-user-name {
    font-weight: 600;
    font-size: 0.88rem;
    color: var(--text-heading, #1e1e2d);
  }

  .table-user-email {
    font-size: 0.78rem;
    color: var(--text-muted, #a2a5b9);
  }

  .date-cell {
    font-size: 0.82rem;
    color: var(--text-secondary, #6c7293);
  }

  .table-actions {
    display: flex;
    gap: 4px;
  }

  .table-action-btn {
    width: 30px;
    height: 30px;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted, #a2a5b9);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
  }

  .table-action-btn:hover {
    color: #6941C6;
    border-color: #6941C6;
  }

  .table-action-btn.danger:hover {
    color: #e53e3e;
    border-color: #e53e3e;
  }

  /* ── Modal ── */
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(2px);
  }

  .modal-card {
    width: 500px;
    max-width: 95vw;
    background: var(--bg-card, #fff);
    border-radius: 12px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
    overflow: hidden;
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--border-subtle, #e4e6ef);
  }

  .modal-header h3 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text-heading, #1e1e2d);
  }

  .modal-close {
    cursor: pointer;
    color: var(--text-muted, #a2a5b9);
    display: flex;
  }

  .modal-close:hover { color: var(--text-heading, #1e1e2d); }

  .modal-body {
    padding: 1.25rem;
  }

  .modal-error {
    background: #fff5f5;
    color: #e53e3e;
    padding: 0.65rem 0.85rem;
    border-radius: 8px;
    margin-bottom: 1rem;
    font-size: 0.82rem;
    border: 1px solid rgba(229, 62, 62, 0.2);
  }

  .modal-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  .modal-field {
    margin-bottom: 1rem;
  }

  .modal-field label {
    display: block;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-secondary, #6c7293);
    margin-bottom: 0.4rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .field-hint {
    font-weight: 400;
    text-transform: none;
    letter-spacing: normal;
    font-size: 0.72rem;
    color: var(--text-muted, #a2a5b9);
  }

  .modal-field input,
  .modal-field select {
    width: 100%;
    padding: 0.6rem 0.85rem;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 8px;
    font-size: 0.88rem;
    background: var(--bg-card, #fff);
    color: var(--text-heading, #1e1e2d);
    font-family: inherit;
  }

  .modal-field input:focus,
  .modal-field select:focus {
    outline: none;
    border-color: #6941C6;
    box-shadow: 0 0 0 3px rgba(105, 65, 198, 0.1);
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    padding: 0.85rem 1.25rem;
    border-top: 1px solid var(--border-subtle, #e4e6ef);
    background: var(--bg-base, #f5f5f9);
  }

  .modal-cancel {
    padding: 0.55rem 1.15rem;
    border: 1px solid var(--border-subtle, #e4e6ef);
    border-radius: 8px;
    background: var(--bg-card, #fff);
    color: var(--text-secondary, #6c7293);
    font-size: 0.85rem;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.15s;
  }

  .modal-cancel:hover {
    background: var(--bg-base, #f5f5f9);
  }

  .modal-save {
    padding: 0.55rem 1.25rem;
    background: linear-gradient(135deg, #452B90, #6941C6);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.2s;
  }

  .modal-save:hover:not(:disabled) {
    box-shadow: 0 4px 14px rgba(105, 65, 198, 0.4);
  }

  .modal-save:disabled { opacity: 0.5; cursor: not-allowed; }

  @media (max-width: 768px) {
    .stats-row { grid-template-columns: repeat(2, 1fr); }
    .manager-header { flex-direction: column; align-items: stretch; }
    .header-right { flex-wrap: wrap; }
    .header-search input { width: 100%; }
  }
</style>
