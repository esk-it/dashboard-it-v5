<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { currentPage, navItems, sidebarOpen } from '../stores/navigation.js';
  import { theme, toggleTheme } from '../stores/theme.js';
  import { currentUser, logout } from '../stores/auth.js';
  import { api } from '../api/client.js';
  import { Home, Search, Sun, Moon, Bell, Mail, ChevronDown, Lock, LogOut, User, CalendarDays } from 'lucide-svelte';
  import { success, error as toastError, info } from '../stores/toast.js';

  const dispatch = createEventDispatcher();

  let showUserDropdown = false;
  let showNotifDropdown = false;
  let showMailDropdown = false;
  let showCalDropdown = false;

  // Data for dropdowns
  let unreadMails = [];
  let unreadCount = 0;
  let upcomingEvents = [];
  let todayEventCount = 0;

  // Change detection for notifications
  let prevUnreadCount = -1; // -1 = first load, skip notification
  let prevProblemCount = -1;
  let overdueTasks = [];
  let refreshTimer;

  // Get current page label for breadcrumb
  $: currentLabel = navItems.find(i => i.path === $currentPage)?.label || 'Dashboard';
  $: totalNotifCount = todayEventCount + overdueTasks.length;

  function handleLogout() {
    showUserDropdown = false;
    logout();
  }

  function handleLock() {
    showUserDropdown = false;
    dispatch('lock');
  }

  function getInitials(user) {
    if (!user) return 'AD';
    const name = user.display_name || user.username || '';
    return name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase() || 'AD';
  }

  function closeAllDropdowns() {
    showUserDropdown = false;
    showNotifDropdown = false;
    showMailDropdown = false;
    showCalDropdown = false;
  }

  function toggleDropdown(which) {
    const wasOpen = which === 'notif' ? showNotifDropdown : which === 'mail' ? showMailDropdown : which === 'cal' ? showCalDropdown : showUserDropdown;
    closeAllDropdowns();
    if (which === 'notif') showNotifDropdown = !wasOpen;
    else if (which === 'mail') showMailDropdown = !wasOpen;
    else if (which === 'cal') showCalDropdown = !wasOpen;
    else if (which === 'user') showUserDropdown = !wasOpen;
  }

  // ── Data fetching ──
  async function triggerMailSync() {
    // Background sync: trigger incremental sync then refresh preview
    try { await api.post('/api/gmail/sync'); } catch {}
  }

  async function fetchMailPreview() {
    try {
      const { count } = await api.get('/api/gmail/unread-count');
      const newCount = count || 0;
      // Detect new unread mails (skip first load)
      if (prevUnreadCount >= 0 && newCount > prevUnreadCount) {
        const diff = newCount - prevUnreadCount;
        info(`${diff} nouveau${diff > 1 ? 'x' : ''} mail${diff > 1 ? 's' : ''} non lu${diff > 1 ? 's' : ''}`);
      }
      prevUnreadCount = newCount;
      unreadCount = newCount;
      if (unreadCount > 0) {
        const data = await api.get('/api/gmail/messages?folder=inbox&max_results=5');
        unreadMails = (data.messages || []).filter(m => m.unread).slice(0, 5);
      } else {
        unreadMails = [];
      }
    } catch {
      unreadCount = 0;
      unreadMails = [];
    }
  }

  async function fetchCalendarPreview() {
    try {
      const now = new Date();
      const start = now.toISOString().slice(0, 10);
      const end = new Date(now.getTime() + 7 * 86400000).toISOString().slice(0, 10);
      const data = await api.get(`/api/google-calendar/events?start=${start}&end=${end}`);
      const allEvents = data.events || [];
      // Sort by date
      allEvents.sort((a, b) => (a.date_start || '').localeCompare(b.date_start || ''));
      upcomingEvents = allEvents.slice(0, 5);
      // Count today's events
      todayEventCount = allEvents.filter(e => (e.date_start || '').startsWith(start)).length;
    } catch {
      upcomingEvents = [];
      todayEventCount = 0;
    }
  }

  async function fetchOverdueTasks() {
    try {
      const data = await api.get('/api/dashboard/kpis');
      if (data.overdue_tasks > 0) {
        const tasks = await api.get('/api/dashboard/top-tasks');
        const today = new Date().toISOString().slice(0, 10);
        // Tasks are overdue if due_date is before today
        overdueTasks = (tasks || []).filter(t => t.due_date && t.due_date < today).slice(0, 5);
      } else {
        overdueTasks = [];
      }
    } catch { overdueTasks = []; }
  }

  async function fetchMonitoringAlerts() {
    try {
      const stats = await api.get('/api/monitoring/stats');
      const problemCount = stats.active_problems || 0;
      // Detect new critical problems (skip first load)
      if (prevProblemCount >= 0 && problemCount > prevProblemCount) {
        const diff = problemCount - prevProblemCount;
        toastError(`${diff} nouvelle${diff > 1 ? 's' : ''} alerte${diff > 1 ? 's' : ''} monitoring !`);
      }
      prevProblemCount = problemCount;
    } catch { /* monitoring not configured, ignore */ }
  }

  async function fetchAll() {
    await Promise.all([fetchMailPreview(), fetchCalendarPreview(), fetchOverdueTasks(), fetchMonitoringAlerts()]);
  }

  async function syncAndRefresh() {
    await triggerMailSync();
    await fetchAll();
  }

  // Helpers
  function parseFromName(from) {
    if (!from) return 'Inconnu';
    const match = from.match(/^"?([^"<]+?)"?\s*</) || from.match(/^([^<@]+)/);
    return match ? match[1].trim() || from.split('@')[0] : from.split('@')[0] || 'Inconnu';
  }

  function formatRelativeDate(internalDate) {
    if (!internalDate) return '';
    const d = new Date(Number(internalDate));
    const now = new Date();
    const diffH = (now - d) / 3600000;
    if (diffH < 1) return `${Math.floor((now - d) / 60000)}min`;
    if (diffH < 24 && d.getDate() === now.getDate()) return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
  }

  function formatEventDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) return "Aujourd'hui";
    const tomorrow = new Date(now); tomorrow.setDate(now.getDate() + 1);
    if (d.toDateString() === tomorrow.toDateString()) return 'Demain';
    return d.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' });
  }

  function formatEventTime(timeStr) {
    if (!timeStr) return 'Journee';
    return timeStr.slice(0, 5);
  }

  onMount(() => {
    // Initial: trigger background mail sync + fetch all previews
    syncAndRefresh();
    // Auto-refresh every 15s (sync mail + update badges)
    refreshTimer = setInterval(syncAndRefresh, 15000);
  });

  onDestroy(() => {
    if (refreshTimer) clearInterval(refreshTimer);
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="header" class:sidebar-open={$sidebarOpen}>
  <div class="header-content">
    <!-- Left: Breadcrumb -->
    <div class="header-left">
      <div class="page-titles">
        <h5 class="bc-title">Dashboard</h5>
        <ol class="breadcrumb">
          <li class="breadcrumb-item">
            <Home size={16} />
            <span>Home</span>
          </li>
          <li class="breadcrumb-item active">{currentLabel}</li>
        </ol>
      </div>
    </div>

    <!-- Right: Search, Theme, Notifications, Profile -->
    <div class="header-right">
      <!-- Search -->
      <div class="search-area" on:click={() => dispatch('search')}>
        <input type="text" class="search-input" placeholder="Search here..." readonly />
        <span class="search-icon">
          <Search size={18} />
        </span>
      </div>

      <!-- Theme toggle -->
      <div class="header-icon" on:click={toggleTheme} title={$theme === 'glass' ? 'Mode clair' : 'Mode sombre'}>
        {#if $theme === 'glass'}
          <Moon size={20} />
        {:else}
          <Sun size={20} />
        {/if}
      </div>

      <!-- ═══ Notifications (Bell) ═══ -->
      <div class="header-icon-wrapper">
        <div class="header-icon" on:click={() => toggleDropdown('notif')}>
          <Bell size={20} />
          {#if totalNotifCount > 0}
            <span class="icon-badge">{totalNotifCount > 99 ? '99+' : totalNotifCount}</span>
          {/if}
        </div>
        {#if showNotifDropdown}
          <div class="icon-dropdown">
            <div class="icon-dropdown__header">
              <span class="icon-dropdown__title">Notifications</span>
              {#if totalNotifCount > 0}
                <span class="icon-dropdown__count">{totalNotifCount}</span>
              {/if}
            </div>
            <div class="icon-dropdown__list">
              {#if overdueTasks.length === 0 && upcomingEvents.filter(e => (e.date_start || '').startsWith(new Date().toISOString().slice(0,10))).length === 0}
                <div class="icon-dropdown__empty">Aucune notification</div>
              {/if}
              {#each overdueTasks.slice(0, 5) as task}
                <div class="icon-dropdown__item" on:click={() => { closeAllDropdowns(); currentPage.set('/tasks'); }}>
                  <div class="icon-dropdown__item-icon" style="background:rgba(239,68,68,0.1);color:#EF4444">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  </div>
                  <div class="icon-dropdown__item-content">
                    <span class="icon-dropdown__item-title">Tache en retard</span>
                    <span class="icon-dropdown__item-sub">{task.title || '(sans titre)'}</span>
                  </div>
                  <span class="icon-dropdown__item-time" style="color:#EF4444">{task.due_date || ''}</span>
                </div>
              {/each}
              {#each upcomingEvents.filter(e => (e.date_start || '').startsWith(new Date().toISOString().slice(0,10))).slice(0, 3) as evt}
                <div class="icon-dropdown__item" on:click={() => { closeAllDropdowns(); currentPage.set('/planning'); }}>
                  <div class="icon-dropdown__item-icon" style="background:rgba(139,92,246,0.1);color:#8B5CF6">
                    <CalendarDays size={14} />
                  </div>
                  <div class="icon-dropdown__item-content">
                    <span class="icon-dropdown__item-title">{evt.title || '(sans titre)'}</span>
                    <span class="icon-dropdown__item-sub">{formatEventTime(evt.time_start)}</span>
                  </div>
                  <span class="icon-dropdown__item-time">Aujourd'hui</span>
                </div>
              {/each}
            </div>
            <div class="icon-dropdown__footer" on:click={() => { closeAllDropdowns(); currentPage.set('/email'); }}>
              Voir tout
            </div>
          </div>
        {/if}
      </div>

      <!-- ═══ Mail (Envelope) ═══ -->
      <div class="header-icon-wrapper">
        <div class="header-icon" on:click={() => toggleDropdown('mail')}>
          <Mail size={20} />
          {#if unreadCount > 0}
            <span class="icon-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
          {/if}
        </div>
        {#if showMailDropdown}
          <div class="icon-dropdown">
            <div class="icon-dropdown__header">
              <span class="icon-dropdown__title">Emails</span>
              {#if unreadCount > 0}
                <span class="icon-dropdown__count">{unreadCount} non lu{unreadCount > 1 ? 's' : ''}</span>
              {/if}
            </div>
            <div class="icon-dropdown__list">
              {#if unreadMails.length === 0}
                <div class="icon-dropdown__empty">Aucun email non lu</div>
              {/if}
              {#each unreadMails as mail}
                <div class="icon-dropdown__item" on:click={() => { closeAllDropdowns(); currentPage.set('/email'); }}>
                  <div class="icon-dropdown__item-avatar" style="background:{getAvatarColor(parseFromName(mail.from))}">
                    {parseFromName(mail.from).charAt(0).toUpperCase()}
                  </div>
                  <div class="icon-dropdown__item-content">
                    <span class="icon-dropdown__item-title">{parseFromName(mail.from)}</span>
                    <span class="icon-dropdown__item-sub">{mail.subject || '(sans objet)'}</span>
                  </div>
                  <span class="icon-dropdown__item-time">{formatRelativeDate(mail.internalDate)}</span>
                </div>
              {/each}
            </div>
            <div class="icon-dropdown__footer" on:click={() => { closeAllDropdowns(); currentPage.set('/email'); }}>
              Voir toute la boite mail
            </div>
          </div>
        {/if}
      </div>

      <!-- ═══ Calendar ═══ -->
      <div class="header-icon-wrapper">
        <div class="header-icon" on:click={() => toggleDropdown('cal')}>
          <CalendarDays size={20} />
          {#if todayEventCount > 0}
            <span class="icon-badge">{todayEventCount}</span>
          {/if}
        </div>
        {#if showCalDropdown}
          <div class="icon-dropdown">
            <div class="icon-dropdown__header">
              <span class="icon-dropdown__title">Agenda</span>
              {#if todayEventCount > 0}
                <span class="icon-dropdown__count">{todayEventCount} aujourd'hui</span>
              {/if}
            </div>
            <div class="icon-dropdown__list">
              {#if upcomingEvents.length === 0}
                <div class="icon-dropdown__empty">Aucun evenement a venir</div>
              {/if}
              {#each upcomingEvents as evt}
                <div class="icon-dropdown__item" on:click={() => { closeAllDropdowns(); currentPage.set('/planning'); }}>
                  <div class="icon-dropdown__item-icon" style="background:rgba(139,92,246,0.1);color:#8B5CF6">
                    <CalendarDays size={14} />
                  </div>
                  <div class="icon-dropdown__item-content">
                    <span class="icon-dropdown__item-title">{evt.title || '(sans titre)'}</span>
                    <span class="icon-dropdown__item-sub">{formatEventDate(evt.date_start)} {evt.all_day ? '' : formatEventTime(evt.time_start)}</span>
                  </div>
                </div>
              {/each}
            </div>
            <div class="icon-dropdown__footer" on:click={() => { closeAllDropdowns(); currentPage.set('/planning'); }}>
              Voir le planning
            </div>
          </div>
        {/if}
      </div>

      <!-- Profile dropdown -->
      <div class="profile-dropdown" on:click={() => toggleDropdown('user')}>
        <div class="profile-avatar" style="background:{$currentUser?.avatar_color || 'var(--primary)'}">
          {getInitials($currentUser)}
        </div>
        {#if $sidebarOpen}
          <span class="profile-name">{$currentUser?.display_name || 'Administrateur'}</span>
        {/if}
        <ChevronDown size={14} />

        {#if showUserDropdown}
          <div class="dropdown-menu">
            <div class="dropdown-item" on:click={() => { showUserDropdown = false; currentPage.set('/settings'); }}>
              <User size={16} /> Profil
            </div>
            <div class="dropdown-item" on:click={handleLock}>
              <Lock size={16} /> Verrouiller
            </div>
            <div class="dropdown-divider"></div>
            <div class="dropdown-item text-danger" on:click={handleLogout}>
              <LogOut size={16} /> Déconnexion
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>

{#if showUserDropdown || showNotifDropdown || showMailDropdown || showCalDropdown}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="dropdown-backdrop" on:click={closeAllDropdowns}></div>
{/if}

<script context="module">
  function getAvatarColor(name) {
    let hash = 0;
    for (const c of name) hash = c.charCodeAt(0) + ((hash << 5) - hash);
    const colors = ['#8869e1', '#F59E0B', '#3A9B94', '#EC4899', '#3B82F6', '#EF4444', '#22C55E'];
    return colors[Math.abs(hash) % colors.length];
  }
</script>

<style>
  /* ═══════════════════════════════════════
     HEADER — YashAdmin exact
     Height: 4.375rem (70px)
     padding-left: 15rem (sidebar width)
     ═══════════════════════════════════════ */
  .header {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: var(--header-height);
    z-index: 3;
    background: var(--bg-card);
    padding-left: var(--sidebar-width);
    transition: all 0.2s ease;
    border-bottom: 1px solid var(--border-subtle);
  }

  .header:not(.sidebar-open) {
    padding-left: var(--sidebar-width-collapsed);
  }

  .header-content {
    height: 100%;
    padding: 0 2.075rem 0 2.1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  /* ── Left: Breadcrumb ── */
  .header-left {
    display: flex;
    align-items: center;
  }

  .page-titles {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .bc-title {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-heading);
    margin: 0;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: 0.8125rem;
  }

  .breadcrumb-item {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    color: var(--text-muted);
  }

  .breadcrumb-item + .breadcrumb-item::before {
    content: '/';
    color: var(--text-muted);
    margin-right: 0.25rem;
  }

  .breadcrumb-item.active {
    color: var(--primary);
  }

  /* ── Right: Actions ── */
  .header-right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  /* Search bar */
  .search-area {
    display: flex;
    align-items: center;
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: 2.5rem;
    padding: 0 0.25rem 0 1.25rem;
    cursor: pointer;
    transition: border-color 0.2s ease;
    gap: 0.5rem;
  }

  .search-area:hover {
    border-color: var(--primary);
  }

  .search-input {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    outline: none;
    font-size: 0.875rem;
    color: var(--text-primary) !important;
    padding: 0.5rem 0;
    width: 12rem;
    cursor: pointer;
    font-family: 'Poppins', sans-serif;
  }

  .search-icon {
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 50%;
    background: var(--primary);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background 0.2s ease;
  }

  .search-area:hover .search-icon {
    background: var(--primary-hover);
  }

  /* Header icons */
  .header-icon-wrapper {
    position: relative;
  }

  .header-icon {
    width: 2.75rem;
    height: 2.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    cursor: pointer;
    color: var(--text-heading);
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    transition: all 0.2s ease;
    position: relative;
  }

  .header-icon:hover {
    background: var(--primary);
    color: #fff;
    border-color: var(--primary);
  }

  /* Badge */
  .icon-badge {
    position: absolute;
    top: -2px;
    right: -2px;
    min-width: 18px;
    height: 18px;
    background: #EF4444;
    color: #fff;
    font-size: 0.625rem;
    font-weight: 700;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 4px;
    line-height: 1;
    border: 2px solid var(--bg-card);
  }

  /* ── Icon dropdown ── */
  .icon-dropdown {
    position: absolute;
    top: calc(100% + 0.5rem);
    right: -1rem;
    width: 22rem;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 0.75rem;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
    z-index: 100;
    overflow: hidden;
    animation: dropdownIn 0.15s ease-out;
  }

  @keyframes dropdownIn {
    from { opacity: 0; transform: translateY(-8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .icon-dropdown__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.875rem 1rem;
    border-bottom: 1px solid var(--border-subtle);
  }

  .icon-dropdown__title {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-heading);
  }

  .icon-dropdown__count {
    font-size: 0.75rem;
    color: var(--primary);
    font-weight: 500;
  }

  .icon-dropdown__list {
    max-height: 320px;
    overflow-y: auto;
  }

  .icon-dropdown__empty {
    padding: 2rem 1rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8125rem;
  }

  .icon-dropdown__item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    cursor: pointer;
    transition: background 0.1s ease;
  }

  .icon-dropdown__item:hover {
    background: var(--bg-hover);
  }

  .icon-dropdown__item-icon {
    width: 2rem;
    height: 2rem;
    border-radius: 0.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .icon-dropdown__item-avatar {
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: #fff;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .icon-dropdown__item-content {
    flex: 1;
    min-width: 0;
  }

  .icon-dropdown__item-title {
    display: block;
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--text-heading);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .icon-dropdown__item-sub {
    display: block;
    font-size: 0.75rem;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-top: 1px;
  }

  .icon-dropdown__item-time {
    font-size: 0.6875rem;
    color: var(--text-muted);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .icon-dropdown__footer {
    padding: 0.75rem 1rem;
    text-align: center;
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--primary);
    cursor: pointer;
    border-top: 1px solid var(--border-subtle);
    transition: background 0.1s ease;
  }

  .icon-dropdown__footer:hover {
    background: rgba(var(--primary-rgb, 99, 102, 241), 0.05);
  }

  /* Profile dropdown */
  .profile-dropdown {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    border-radius: 0.625rem;
    transition: background 0.2s ease;
    position: relative;
    margin-left: 0.5rem;
  }

  .profile-dropdown:hover {
    background: var(--bg-hover);
  }

  .profile-avatar {
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 50%;
    /* background set inline from user.avatar_color */
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 600;
    flex-shrink: 0;
  }

  .profile-name {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-heading);
    white-space: nowrap;
  }

  /* Dropdown menu */
  .dropdown-menu {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 0.5rem;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 0.625rem;
    box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, 0.15);
    min-width: 12rem;
    padding: 0.5rem 0;
    z-index: 100;
  }

  .dropdown-item {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.625rem 1.25rem;
    font-size: 0.875rem;
    color: var(--text-primary);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .dropdown-item:hover {
    background: var(--bg-hover);
    color: var(--primary);
  }

  .dropdown-item.text-danger {
    color: var(--danger);
  }

  .dropdown-item.text-danger:hover {
    background: rgba(var(--danger-rgb), 0.1);
    color: var(--danger);
  }

  .dropdown-divider {
    height: 1px;
    background: var(--border-subtle);
    margin: 0.25rem 0;
  }

  .dropdown-backdrop {
    position: fixed;
    inset: 0;
    z-index: 2;
  }
</style>
