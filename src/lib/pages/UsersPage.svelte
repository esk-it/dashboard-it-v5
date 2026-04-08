<script>
  import { onMount } from 'svelte';
  import { api } from '../api/client.js';
  import { currentUser } from '../stores/auth.js';

  let users = [];
  let loading = true;
  let viewMode = 'grid'; // 'grid' | 'list'

  // Modal state
  let showModal = false;
  let modalMode = 'add'; // 'add' | 'edit'
  let editingUser = null;
  let form = { username: '', email: '', display_name: '', password: '', role: 'user', avatar_color: '#8869e1' };
  let saving = false;
  let error = '';

  const COLORS = ['#8869e1', '#F59E0B', '#3A9B94', '#EC4899', '#3B82F6', '#EF4444', '#22C55E', '#06B6D4'];
  const ROLES = [
    { value: 'admin', label: 'Administrateur' },
    { value: 'user', label: 'Utilisateur' },
  ];

  async function fetchUsers() {
    loading = true;
    try {
      const data = await api.get('/api/auth/users');
      users = data.users || [];
    } catch (e) {
      console.error('Failed to fetch users', e);
    }
    loading = false;
  }

  function openAddModal() {
    modalMode = 'add';
    editingUser = null;
    form = { username: '', email: '', display_name: '', password: '', role: 'user', avatar_color: COLORS[Math.floor(Math.random() * COLORS.length)] };
    error = '';
    showModal = true;
  }

  function openEditModal(user) {
    modalMode = 'edit';
    editingUser = user;
    form = { username: user.username, email: user.email, display_name: user.display_name, password: '', role: user.role, avatar_color: user.avatar_color };
    error = '';
    showModal = true;
  }

  async function saveUser() {
    saving = true;
    error = '';
    try {
      if (modalMode === 'add') {
        if (!form.username || !form.password) { error = 'Nom d\'utilisateur et mot de passe requis'; saving = false; return; }
        await api.post('/api/auth/users', {
          username: form.username,
          email: form.email,
          password: form.password,
          display_name: form.display_name || form.username,
        });
      } else {
        const payload = {
          email: form.email,
          display_name: form.display_name,
          role: form.role,
          avatar_color: form.avatar_color,
        };
        if (form.password) payload.password = form.password;
        await api.put(`/api/auth/users/${editingUser.id}`, payload);
      }
      showModal = false;
      await fetchUsers();
    } catch (e) {
      error = e.message || 'Erreur';
    }
    saving = false;
  }

  async function deleteUser(user) {
    if (!confirm(`Supprimer l'utilisateur "${user.display_name}" ?`)) return;
    try {
      await api.delete(`/api/auth/users/${user.id}`);
      await fetchUsers();
    } catch (e) {
      alert(e.message || 'Erreur');
    }
  }

  async function toggleActive(user) {
    try {
      await api.put(`/api/auth/users/${user.id}`, { is_active: !user.is_active });
      await fetchUsers();
    } catch (e) {
      alert(e.message || 'Erreur');
    }
  }

  function getInitials(name) {
    if (!name) return '?';
    return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  }

  function formatDate(iso) {
    if (!iso) return 'Jamais';
    try {
      return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch { return iso; }
  }

  onMount(fetchUsers);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="users-page">
  <div class="users-header">
    <h2>Utilisateurs</h2>
    <div class="users-header-actions">
      <div class="view-toggle">
        <button class="view-btn" class:active={viewMode === 'list'} on:click={() => viewMode = 'list'} title="Liste">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
        </button>
        <button class="view-btn" class:active={viewMode === 'grid'} on:click={() => viewMode = 'grid'} title="Grille">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
        </button>
      </div>
      <button class="add-user-btn" on:click={openAddModal}>+ Ajouter</button>
    </div>
  </div>

  {#if loading}
    <div class="users-loading">Chargement...</div>
  {:else if viewMode === 'grid'}
    <!-- ═══ Grid View (YashAdmin style) ═══ -->
    <div class="users-grid">
      {#each users as user (user.id)}
        <div class="user-card" class:user-card--inactive={!user.is_active}>
          <div class="user-card__avatar" style="background:{user.avatar_color}">
            {getInitials(user.display_name)}
            <span class="user-card__status" class:online={user.is_active}></span>
          </div>
          <h4 class="user-card__name">{user.display_name}</h4>
          <p class="user-card__email">{user.email || '-'}</p>

          <div class="user-card__stats">
            <div class="user-card__stat">
              <span class="user-card__stat-value">{user.role === 'admin' ? 'Admin' : 'User'}</span>
              <span class="user-card__stat-label">role</span>
            </div>
            <div class="user-card__stat">
              <span class="user-card__stat-value">{formatDate(user.created_at)}</span>
              <span class="user-card__stat-label">inscription</span>
            </div>
          </div>

          <p class="user-card__meta">Derniere connexion : {formatDate(user.last_login)}</p>

          <div class="user-card__actions">
            <button class="user-card__btn user-card__btn--edit" on:click={() => openEditModal(user)}>Modifier</button>
            {#if user.id !== $currentUser?.id}
              <button class="user-card__btn user-card__btn--toggle" on:click={() => toggleActive(user)}>
                {user.is_active ? 'Desactiver' : 'Activer'}
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>

  {:else}
    <!-- ═══ List View ═══ -->
    <div class="users-table-wrap">
      <table class="users-table">
        <thead>
          <tr>
            <th>Utilisateur</th>
            <th>Email</th>
            <th>Role</th>
            <th>Statut</th>
            <th>Derniere connexion</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each users as user (user.id)}
            <tr class:inactive={!user.is_active}>
              <td>
                <div class="user-row-info">
                  <div class="user-row-avatar" style="background:{user.avatar_color}">{getInitials(user.display_name)}</div>
                  <div>
                    <span class="user-row-name">{user.display_name}</span>
                    <span class="user-row-username">@{user.username}</span>
                  </div>
                </div>
              </td>
              <td>{user.email || '-'}</td>
              <td><span class="role-badge" class:admin={user.role === 'admin'}>{user.role === 'admin' ? 'Admin' : 'User'}</span></td>
              <td><span class="status-dot" class:active={user.is_active}></span> {user.is_active ? 'Actif' : 'Inactif'}</td>
              <td>{formatDate(user.last_login)}</td>
              <td>
                <button class="tbl-btn" on:click={() => openEditModal(user)} title="Modifier">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                {#if user.id !== $currentUser?.id}
                  <button class="tbl-btn tbl-btn--danger" on:click={() => deleteUser(user)} title="Supprimer">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- ═══ Add/Edit User Modal ═══ -->
{#if showModal}
  <div class="modal-overlay" on:click={() => showModal = false}>
    <div class="modal-box" on:click|stopPropagation>
      <h3>{modalMode === 'add' ? 'Ajouter un utilisateur' : `Modifier ${editingUser?.display_name}`}</h3>

      {#if error}
        <div class="modal-error">{error}</div>
      {/if}

      <div class="modal-form">
        {#if modalMode === 'add'}
          <label>
            <span>Nom d'utilisateur *</span>
            <input type="text" bind:value={form.username} placeholder="john.doe" />
          </label>
        {/if}
        <label>
          <span>Nom complet</span>
          <input type="text" bind:value={form.display_name} placeholder="John Doe" />
        </label>
        <label>
          <span>Email</span>
          <input type="email" bind:value={form.email} placeholder="john@example.com" />
        </label>
        <label>
          <span>{modalMode === 'add' ? 'Mot de passe *' : 'Nouveau mot de passe (vide = inchange)'}</span>
          <input type="password" bind:value={form.password} placeholder="********" />
        </label>
        {#if modalMode === 'edit'}
          <label>
            <span>Role</span>
            <select bind:value={form.role}>
              {#each ROLES as r}
                <option value={r.value}>{r.label}</option>
              {/each}
            </select>
          </label>
          <label>
            <span>Couleur avatar</span>
            <div class="color-picker">
              {#each COLORS as c}
                <button class="color-dot" class:active={form.avatar_color === c} style="background:{c}" on:click={() => form.avatar_color = c}></button>
              {/each}
            </div>
          </label>
        {/if}
      </div>

      <div class="modal-actions">
        <button class="ya-btn ya-btn--primary" on:click={saveUser} disabled={saving}>
          {saving ? 'En cours...' : modalMode === 'add' ? 'Ajouter' : 'Enregistrer'}
        </button>
        <button class="ya-btn" on:click={() => showModal = false}>Annuler</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .users-page { animation: fadeIn 0.3s ease-out; }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

  .users-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 1.5rem;
  }
  .users-header h2 { font-size: 1.25rem; font-weight: 700; color: var(--text-heading); margin: 0; }
  .users-header-actions { display: flex; align-items: center; gap: 0.75rem; }

  .view-toggle { display: flex; background: var(--bg-base); border: 1px solid var(--border-subtle); border-radius: 0.5rem; overflow: hidden; }
  .view-btn {
    padding: 0.5rem 0.625rem; background: none; border: none; cursor: pointer;
    color: var(--text-muted); transition: all 0.15s;
  }
  .view-btn.active { background: var(--primary); color: #fff; }
  .view-btn:hover:not(.active) { background: var(--bg-hover); }

  .add-user-btn {
    padding: 0.5rem 1.25rem; background: var(--primary); color: #fff; border: none;
    border-radius: 0.5rem; font-weight: 600; cursor: pointer; font-family: inherit; font-size: 0.875rem;
    transition: filter 0.15s;
  }
  .add-user-btn:hover { filter: brightness(1.1); }

  /* ── Grid View ── */
  .users-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1.25rem;
  }
  .user-card {
    background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 0.75rem;
    padding: 1.5rem; text-align: center; transition: transform 0.2s, box-shadow 0.2s;
  }
  .user-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
  .user-card--inactive { opacity: 0.5; }

  .user-card__avatar {
    width: 5rem; height: 5rem; border-radius: 50%; margin: 0 auto 1rem;
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-size: 1.5rem; font-weight: 700; position: relative;
  }
  .user-card__status {
    position: absolute; bottom: 2px; right: 2px; width: 14px; height: 14px;
    border-radius: 50%; border: 2px solid var(--bg-card);
    background: #EF4444;
  }
  .user-card__status.online { background: #22C55E; }

  .user-card__name { font-size: 1rem; font-weight: 600; color: var(--text-heading); margin: 0 0 0.25rem; }
  .user-card__email { font-size: 0.8125rem; color: var(--text-muted); margin: 0 0 1rem; }

  .user-card__stats {
    display: flex; justify-content: center; gap: 1.5rem;
    padding: 0.75rem 0; border-top: 1px solid var(--border-subtle); border-bottom: 1px solid var(--border-subtle);
    margin-bottom: 0.75rem;
  }
  .user-card__stat { text-align: center; }
  .user-card__stat-value { display: block; font-size: 0.875rem; font-weight: 600; color: var(--primary); }
  .user-card__stat-label { font-size: 0.6875rem; color: var(--text-muted); text-transform: uppercase; }

  .user-card__meta { font-size: 0.75rem; color: var(--text-muted); margin: 0 0 1rem; }

  .user-card__actions { display: flex; justify-content: center; gap: 0.5rem; }
  .user-card__btn {
    padding: 0.375rem 1rem; border-radius: 0.375rem; font-size: 0.8125rem;
    font-weight: 600; cursor: pointer; border: none; font-family: inherit; transition: filter 0.15s;
  }
  .user-card__btn--edit { background: var(--primary); color: #fff; }
  .user-card__btn--toggle { background: rgba(var(--primary-rgb, 99,102,241), 0.1); color: var(--primary); }
  .user-card__btn:hover { filter: brightness(1.1); }

  /* ── List View ── */
  .users-table-wrap { overflow-x: auto; }
  .users-table {
    width: 100%; border-collapse: separate; border-spacing: 0;
    background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 0.75rem; overflow: hidden;
  }
  .users-table th {
    padding: 0.75rem 1rem; text-align: left; font-size: 0.75rem; font-weight: 600;
    color: var(--text-muted); text-transform: uppercase; border-bottom: 1px solid var(--border-subtle);
    background: var(--bg-base);
  }
  .users-table td {
    padding: 0.75rem 1rem; font-size: 0.875rem; color: var(--text-primary);
    border-bottom: 1px solid var(--border-subtle);
  }
  .users-table tr:last-child td { border-bottom: none; }
  .users-table tr.inactive { opacity: 0.5; }

  .user-row-info { display: flex; align-items: center; gap: 0.75rem; }
  .user-row-avatar {
    width: 2.25rem; height: 2.25rem; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-size: 0.75rem; font-weight: 600; flex-shrink: 0;
  }
  .user-row-name { display: block; font-weight: 600; color: var(--text-heading); }
  .user-row-username { font-size: 0.75rem; color: var(--text-muted); }

  .role-badge {
    padding: 0.25rem 0.625rem; border-radius: 1rem; font-size: 0.75rem; font-weight: 600;
    background: rgba(var(--primary-rgb, 99,102,241), 0.1); color: var(--primary);
  }
  .role-badge.admin { background: rgba(245,158,11,0.1); color: #F59E0B; }

  .status-dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    background: #EF4444; margin-right: 4px;
  }
  .status-dot.active { background: #22C55E; }

  .tbl-btn {
    padding: 0.375rem; background: rgba(var(--primary-rgb, 99,102,241), 0.1);
    border: none; border-radius: 0.375rem; cursor: pointer; color: var(--primary); transition: all 0.15s;
  }
  .tbl-btn:hover { background: var(--primary); color: #fff; }
  .tbl-btn--danger { background: rgba(239,68,68,0.1); color: #EF4444; }
  .tbl-btn--danger:hover { background: #EF4444; color: #fff; }

  /* ── Modal ── */
  .modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 9999;
    display: flex; align-items: center; justify-content: center;
    animation: fadeIn 0.15s ease-out;
  }
  .modal-box {
    background: var(--bg-card); border-radius: 0.75rem; padding: 1.5rem;
    width: 90vw; max-width: 480px; box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  }
  .modal-box h3 { margin: 0 0 1rem; font-size: 1.125rem; font-weight: 700; color: var(--text-heading); }
  .modal-error {
    padding: 0.5rem 0.75rem; background: rgba(239,68,68,0.1); color: #EF4444;
    border-radius: 0.375rem; font-size: 0.8125rem; margin-bottom: 1rem;
  }
  .modal-form { display: flex; flex-direction: column; gap: 0.875rem; margin-bottom: 1.25rem; }
  .modal-form label { display: flex; flex-direction: column; gap: 0.25rem; }
  .modal-form label span { font-size: 0.8125rem; font-weight: 600; color: var(--text-muted); }
  .modal-form input, .modal-form select {
    padding: 0.5rem 0.75rem; border: 1px solid var(--border-subtle); border-radius: 0.375rem;
    background: var(--bg-base); color: var(--text-primary); font-family: inherit; font-size: 0.875rem;
  }
  .modal-form input:focus, .modal-form select:focus { outline: none; border-color: var(--primary); }

  .color-picker { display: flex; gap: 0.5rem; margin-top: 0.25rem; }
  .color-dot {
    width: 1.75rem; height: 1.75rem; border-radius: 50%; border: 2px solid transparent;
    cursor: pointer; transition: transform 0.15s;
  }
  .color-dot.active { border-color: var(--text-heading); transform: scale(1.15); }
  .color-dot:hover { transform: scale(1.1); }

  .modal-actions { display: flex; gap: 0.5rem; justify-content: flex-end; }

  .users-loading { text-align: center; padding: 3rem; color: var(--text-muted); }
</style>
