<script>
  import { createEventDispatcher } from 'svelte';
  import { currentPage, navItems, sidebarOpen } from '../stores/navigation.js';
  import { theme, toggleTheme } from '../stores/theme.js';
  import { currentUser, logout } from '../stores/auth.js';
  import { Home, Search, Sun, Moon, Bell, Mail, ChevronDown, Lock, LogOut, User, CalendarDays } from 'lucide-svelte';

  const dispatch = createEventDispatcher();

  let showUserDropdown = false;

  // Get current page label for breadcrumb
  $: currentLabel = navItems.find(i => i.path === $currentPage)?.label || 'Dashboard';

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

      <!-- Notifications -->
      <div class="header-icon">
        <Bell size={20} />
      </div>

      <!-- Mail -->
      <div class="header-icon">
        <Mail size={20} />
      </div>

      <!-- Calendar -->
      <div class="header-icon">
        <CalendarDays size={20} />
      </div>

      <!-- Profile dropdown -->
      <div class="profile-dropdown" on:click={() => showUserDropdown = !showUserDropdown}>
        <div class="profile-avatar">
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

{#if showUserDropdown}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="dropdown-backdrop" on:click={() => showUserDropdown = false}></div>
{/if}

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

  /* Search bar — YashAdmin style: dark bg, colored search icon */
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

  /* Header icons — YashAdmin style: circular with subtle bg */
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
  }

  .header-icon:hover {
    background: var(--primary);
    color: #fff;
    border-color: var(--primary);
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
    background: var(--primary);
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
