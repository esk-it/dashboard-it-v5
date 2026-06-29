<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { currentPage, navItems, sidebarOpen } from '../stores/navigation.js';
  import { theme, toggleTheme } from '../stores/theme.js';
  import { currentUser, logout } from '../stores/auth.js';
  import { isOnline } from '../stores/health.js';
  import { api } from '../api/client.js';
  // v7.6.0 — Modules Email + Planning désactivés : icônes Mail et
  // CalendarDays retirées des imports, ainsi que le toast `mail`.
  import { Home, Search, Sun, Moon, Bell, ChevronDown, Lock, LogOut, User, AlertTriangle, AlertCircle, Info, WifiOff, Activity, Database, HelpCircle } from 'lucide-svelte';
  import HelpModal from './HelpModal.svelte';
  import { success, error as toastError, info as toastInfo, alert_critical as toastCritical } from '../stores/toast.js';

  const dispatch = createEventDispatcher();

  let showUserDropdown = false;
  let showNotifDropdown = false;

  // v7.6.0 — Mail + Calendar dropdowns retirés (modules désactivés).
  // L'état correspondant (showMailDropdown, unreadMails, upcomingEvents, …)
  // a été nettoyé.

  // Change detection for notifications
  let prevProblemCount = -1;
  let overdueTasks = [];
  let refreshTimer;

  // Alert sources beyond tasks/events: live monitoring problem count and the
  // age (in days) of the most recent automatic backup. Computed by fetchAll().
  let monitoringProblems = 0;
  let backupAgeDays = null;  // null = unknown; number = days since last auto backup

  // Get current page label for breadcrumb
  $: currentLabel = navItems.find(i => i.path === $currentPage)?.label || 'Dashboard';
  // v7.4.0 — current module key for the contextual help modal.
  $: currentModuleKey = navItems.find(i => i.path === $currentPage)?.key || 'home';
  let showHelpModal = false;

  // Aggregate alerts grouped by severity. Recomputed reactively from each
  // source. We keep the bell as the single hub for actionable notifications;
  // mail and calendar have their own icons and dropdowns.
  $: criticalAlerts = (() => {
    const out = [];
    if (!$isOnline) {
      out.push({ kind: 'backend', icon: 'WifiOff', title: 'Backend déconnecté', sub: 'Sauvegarde et chargement HS — redémarre l\'app si ça persiste.', target: '/settings' });
    }
    if (monitoringProblems > 0) {
      out.push({ kind: 'monitoring', icon: 'Activity', title: `${monitoringProblems} alerte${monitoringProblems > 1 ? 's' : ''} monitoring`, sub: 'Problèmes actifs sur Zabbix.', target: '/monitoring' });
    }
    return out;
  })();

  $: importantAlerts = (() => {
    const out = [];
    for (const t of overdueTasks.slice(0, 5)) {
      out.push({ kind: 'task', icon: 'AlertTriangle', title: 'Tâche en retard', sub: t.title || '(sans titre)', meta: t.due_date || '', target: '/tasks' });
    }
    if (backupAgeDays !== null && backupAgeDays >= 7) {
      out.push({ kind: 'backup', icon: 'Database', title: `Pas de backup auto depuis ${backupAgeDays} j`, sub: 'Va dans Paramètres pour relancer ou vérifier la config.', target: '/settings' });
    }
    return out;
  })();

  // v7.6.0 — Module Planning désactivé : plus d'alertes "événements
  // du jour" dans la cloche.
  $: infoAlerts = [];

  $: totalNotifCount = criticalAlerts.length + importantAlerts.length + infoAlerts.length;

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
  }

  function toggleDropdown(which) {
    const wasOpen = which === 'notif' ? showNotifDropdown : showUserDropdown;
    closeAllDropdowns();
    if (which === 'notif') showNotifDropdown = !wasOpen;
    else if (which === 'user') showUserDropdown = !wasOpen;
  }

  // ── Data fetching ──
  // v7.6.0 — fetchMailPreview / fetchCalendarPreview / triggerMailSync retirées
  // (modules Email et Planning désactivés).

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
        toastCritical(`${diff} nouvelle${diff > 1 ? 's' : ''} alerte${diff > 1 ? 's' : ''} monitoring !`);
      }
      prevProblemCount = problemCount;
      monitoringProblems = problemCount;
    } catch {
      // monitoring not configured — leave count at 0
      monitoringProblems = 0;
    }
  }

  // Find the most recent automatic backup and surface its age in days. If no
  // auto backups are listed we treat it as a missing backup (very old → 999).
  async function fetchBackupStatus() {
    try {
      const list = await api.get('/api/settings/backups');
      const autos = (list || []).filter(b => b.type === 'Auto');
      if (autos.length === 0) {
        backupAgeDays = 999;
        return;
      }
      // List is already sorted desc by mtime — first is latest.
      const latest = autos[0];
      const ts = new Date(latest.modified).getTime();
      const days = Math.floor((Date.now() - ts) / 86400000);
      backupAgeDays = days >= 0 ? days : 0;
    } catch {
      // Endpoint missing or backend down — leave previous value.
    }
  }

  async function fetchAll() {
    await Promise.all([
      fetchOverdueTasks(),
      fetchMonitoringAlerts(),
      fetchBackupStatus(),
    ]);
  }

  // v7.6.0 — Helpers parseFromName/formatRelativeDate/formatEventDate/Time
  // retirés (utilisés uniquement par les dropdowns Mail et Calendar).

  onMount(() => {
    // Initial fetch (taches en retard, monitoring, backup age)
    fetchAll();
    // Auto-refresh toutes les 30 s
    refreshTimer = setInterval(fetchAll, 30000);
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

      <!-- v7.4.0 — Help button: contextual help for the current module -->
      <div class="header-icon" on:click={() => showHelpModal = true} title="Aide ({currentLabel})">
        <HelpCircle size={20} />
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
          <div class="icon-dropdown alerts-dropdown">
            <div class="icon-dropdown__header">
              <span class="icon-dropdown__title">Alertes</span>
              {#if totalNotifCount > 0}
                <span class="icon-dropdown__count">{totalNotifCount}</span>
              {:else}
                <span class="icon-dropdown__count alerts-count-ok">Tout va bien</span>
              {/if}
            </div>
            <div class="icon-dropdown__list">
              {#if totalNotifCount === 0}
                <div class="icon-dropdown__empty">Aucune alerte — tu peux respirer.</div>
              {/if}

              {#if criticalAlerts.length > 0}
                <div class="alerts-section alerts-section--critical">
                  <span class="alerts-section__dot">🔴</span> Critique
                </div>
                {#each criticalAlerts as a}
                  <div class="icon-dropdown__item alerts-item alerts-item--critical" on:click={() => { closeAllDropdowns(); currentPage.set(a.target); }}>
                    <div class="icon-dropdown__item-icon" style="background:rgba(239,68,68,0.12);color:#EF4444">
                      {#if a.icon === 'WifiOff'}<WifiOff size={14} />{:else if a.icon === 'Activity'}<Activity size={14} />{:else}<AlertCircle size={14} />{/if}
                    </div>
                    <div class="icon-dropdown__item-content">
                      <span class="icon-dropdown__item-title">{a.title}</span>
                      <span class="icon-dropdown__item-sub">{a.sub}</span>
                    </div>
                  </div>
                {/each}
              {/if}

              {#if importantAlerts.length > 0}
                <div class="alerts-section alerts-section--important">
                  <span class="alerts-section__dot">🟡</span> Important
                </div>
                {#each importantAlerts as a}
                  <div class="icon-dropdown__item alerts-item alerts-item--important" on:click={() => { closeAllDropdowns(); currentPage.set(a.target); }}>
                    <div class="icon-dropdown__item-icon" style="background:rgba(245,158,11,0.14);color:#F59E0B">
                      {#if a.icon === 'AlertTriangle'}<AlertTriangle size={14} />{:else if a.icon === 'Database'}<Database size={14} />{:else}<AlertCircle size={14} />{/if}
                    </div>
                    <div class="icon-dropdown__item-content">
                      <span class="icon-dropdown__item-title">{a.title}</span>
                      <span class="icon-dropdown__item-sub">{a.sub}</span>
                    </div>
                    {#if a.meta}
                      <span class="icon-dropdown__item-time" style="color:#F59E0B">{a.meta}</span>
                    {/if}
                  </div>
                {/each}
              {/if}

              {#if infoAlerts.length > 0}
                <div class="alerts-section alerts-section--info">
                  <span class="alerts-section__dot">🔵</span> Info
                </div>
                {#each infoAlerts as a}
                  <div class="icon-dropdown__item alerts-item alerts-item--info" on:click={() => { closeAllDropdowns(); currentPage.set(a.target); }}>
                    <div class="icon-dropdown__item-icon" style="background:rgba(59,130,246,0.12);color:#3B82F6">
                      <CalendarDays size={14} />
                    </div>
                    <div class="icon-dropdown__item-content">
                      <span class="icon-dropdown__item-title">{a.title}</span>
                      <span class="icon-dropdown__item-sub">{a.sub}</span>
                    </div>
                    {#if a.meta}
                      <span class="icon-dropdown__item-time">{a.meta}</span>
                    {/if}
                  </div>
                {/each}
              {/if}
            </div>
          </div>
        {/if}
      </div>

      <!-- v7.6.0 — Icônes Mail + Agenda retirées (modules Email et
           Planning désactivés). On utilise Gmail/Google Calendar dans le
           navigateur, pas besoin du double dans le dashboard. -->

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

{#if showUserDropdown || showNotifDropdown}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="dropdown-backdrop" on:click={closeAllDropdowns}></div>
{/if}

<!-- v7.4.0 — Contextual help modal. Module key derived from $currentPage. -->
<HelpModal bind:open={showHelpModal} moduleKey={currentModuleKey} />

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

  /* ── Alerts panel — severity sections (Critique / Important / Info) ── */
  .alerts-dropdown {
    width: 22.5rem;
  }
  .alerts-count-ok {
    color: #10B981 !important;
  }
  .alerts-section {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.625rem 1rem 0.375rem;
    font-size: 0.6875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    background: var(--bg-base);
    border-top: 1px solid var(--border-subtle);
  }
  .alerts-section:first-child { border-top: none; }
  .alerts-section--critical { color: #EF4444; }
  .alerts-section--important { color: #F59E0B; }
  .alerts-section--info { color: #3B82F6; }
  .alerts-section__dot { font-size: 0.625rem; line-height: 1; }

  /* Subtle left border accent on each item to reinforce severity at a glance */
  .alerts-item--critical { border-left: 3px solid #EF4444; }
  .alerts-item--important { border-left: 3px solid #F59E0B; }
  .alerts-item--info { border-left: 3px solid #3B82F6; }

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
