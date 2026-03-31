<script>
  import { createEventDispatcher } from 'svelte';
  import { currentPage, navItems, sidebarOpen } from '../stores/navigation.js';
  import { theme, toggleTheme } from '../stores/theme.js';
  import { currentUser, logout } from '../stores/auth.js';
  import { Sun, Moon, Search, Bell, Menu, ChevronDown, User, Lock, LogOut } from 'lucide-svelte';

  const dispatch = createEventDispatcher();

  let dropdownOpen = false;

  $: currentLabel = (() => {
    const flat = navItems.filter(i => i.path);
    const found = flat.find(i => i.path === $currentPage);
    return found ? found.label : 'Dashboard';
  })();

  $: userInitials = (() => {
    if (!$currentUser) return '?';
    const name = $currentUser.display_name || $currentUser.username || '';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  })();

  $: displayName = $currentUser?.display_name || $currentUser?.username || 'Utilisateur';

  function handleToggleSidebar() {
    sidebarOpen.update(v => !v);
  }

  function handleSearch() {
    dispatch('search');
  }

  function handleLock() {
    dropdownOpen = false;
    dispatch('lock');
  }

  function handleLogout() {
    dropdownOpen = false;
    logout();
  }

  function toggleDropdown() {
    dropdownOpen = !dropdownOpen;
  }

  function handleClickOutside(e) {
    if (dropdownOpen && !e.target.closest('.user-dropdown-wrapper')) {
      dropdownOpen = false;
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="navbar" on:click={handleClickOutside}>
  <!-- Left side -->
  <div class="navbar-left">
    <button class="navbar-btn hamburger" on:click={handleToggleSidebar} aria-label="Toggle sidebar">
      <Menu size={20} />
    </button>
    <div class="breadcrumb">
      <span class="breadcrumb-prefix">Dashboard</span>
      <span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-current">{currentLabel}</span>
    </div>
  </div>

  <!-- Right side -->
  <div class="navbar-right">
    <button class="navbar-btn" on:click={handleSearch} aria-label="Rechercher" title="Rechercher (Ctrl+K)">
      <Search size={18} />
    </button>

    <button class="navbar-btn" on:click={toggleTheme} aria-label="Changer de thème" title="Changer de thème">
      {#if $theme === 'dark'}
        <Sun size={18} />
      {:else}
        <Moon size={18} />
      {/if}
    </button>

    <button class="navbar-btn notification-btn" aria-label="Notifications" title="Notifications">
      <Bell size={18} />
      <span class="notification-dot"></span>
    </button>

    <!-- User dropdown -->
    <div class="user-dropdown-wrapper">
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="user-trigger" on:click={toggleDropdown}>
        <div class="avatar">{userInitials}</div>
        {#if $sidebarOpen}
          <span class="user-name">{displayName}</span>
          <ChevronDown size={14} />
        {/if}
      </div>

      {#if dropdownOpen}
        <div class="dropdown-menu">
          <div class="dropdown-header">
            <div class="avatar avatar-lg">{userInitials}</div>
            <div class="dropdown-user-info">
              <span class="dropdown-name">{displayName}</span>
              {#if $currentUser?.email}
                <span class="dropdown-email">{$currentUser.email}</span>
              {/if}
            </div>
          </div>
          <div class="dropdown-divider"></div>
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div class="dropdown-item" on:click={() => { dropdownOpen = false; currentPage.set('/settings'); }}>
            <User size={16} />
            <span>Profile</span>
          </div>
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div class="dropdown-item" on:click={handleLock}>
            <Lock size={16} />
            <span>Verrouiller</span>
          </div>
          <div class="dropdown-divider"></div>
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div class="dropdown-item dropdown-item-danger" on:click={handleLogout}>
            <LogOut size={16} />
            <span>Déconnexion</span>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .navbar {
    height: 60px;
    min-height: 60px;
    background: var(--bg-card);
    border-bottom: 1px solid var(--border-subtle);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    z-index: 90;
    font-family: 'Poppins', sans-serif;
  }

  .navbar-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .navbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .navbar-btn {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 8px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s ease, color 0.15s ease;
    position: relative;
  }

  .navbar-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .hamburger {
    display: flex;
  }

  /* Breadcrumb */
  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
  }

  .breadcrumb-prefix {
    color: var(--text-muted);
  }

  .breadcrumb-sep {
    color: var(--text-muted);
  }

  .breadcrumb-current {
    color: var(--text-primary);
    font-weight: 500;
  }

  /* Notification dot */
  .notification-btn {
    position: relative;
  }

  .notification-dot {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 7px;
    height: 7px;
    background: var(--danger);
    border-radius: 50%;
    border: 2px solid var(--bg-card);
  }

  /* User dropdown */
  .user-dropdown-wrapper {
    position: relative;
    margin-left: 8px;
  }

  .user-trigger {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 8px;
    transition: background 0.15s ease;
  }

  .user-trigger:hover {
    background: var(--bg-hover);
  }

  .avatar {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: var(--primary);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .avatar-lg {
    width: 40px;
    height: 40px;
    font-size: 15px;
  }

  .user-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Dropdown menu */
  .dropdown-menu {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    min-width: 220px;
    z-index: 200;
    overflow: hidden;
    animation: dropdownIn 0.15s ease-out;
  }

  @keyframes dropdownIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .dropdown-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
  }

  .dropdown-user-info {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .dropdown-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .dropdown-email {
    font-size: 12px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .dropdown-divider {
    height: 1px;
    background: var(--border-subtle);
  }

  .dropdown-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    cursor: pointer;
    font-size: 13px;
    color: var(--text-secondary);
    transition: background 0.12s ease;
  }

  .dropdown-item:hover {
    background: var(--bg-hover);
  }

  .dropdown-item-danger {
    color: var(--danger);
  }

  .dropdown-item-danger:hover {
    background: rgba(var(--danger-rgb), 0.1);
  }
</style>
