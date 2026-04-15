<script>
  import { onMount, onDestroy } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import { currentPage, navItems, sidebarOpen } from '../stores/navigation.js';
  import { theme, toggleTheme } from '../stores/theme.js';
  import { Home, Globe, Calendar, CheckSquare, FileText, Mail, Users, Monitor, Shield, BookOpen, ClipboardList, Activity, Rocket, Wrench, Settings, Lock, ChevronLeft, Menu } from 'lucide-svelte';
  import logoUrl from '../../assets/logo.png';
  import eskLogoB from '../../assets/ESKlogoB.png';

  const dispatch = createEventDispatcher();

  const iconMap = { Home, Globe, Calendar, CheckSquare, FileText, Mail, Users, Monitor, Shield, BookOpen, ClipboardList, Activity, Rocket, Wrench, Settings };

  let appVersion = '';
  let overdueCount = 0;
  let interval;

  onMount(async () => {
    try {
      const { getVersion } = await import('@tauri-apps/api/app');
      appVersion = await getVersion();
    } catch {
      appVersion = '4.0.1';
    }
    loadOverdueCount();
    interval = setInterval(loadOverdueCount, 60000);
  });

  onDestroy(() => { if (interval) clearInterval(interval); });

  async function loadOverdueCount() {
    try {
      const res = await fetch('http://localhost:8010/api/tasks?status=open');
      const tasks = await res.json();
      const today = new Date().toISOString().slice(0, 10);
      overdueCount = tasks.filter(t => t.due_date && t.due_date < today && !t.done).length;
    } catch { /* ignore */ }
  }

  function navigate(path) {
    currentPage.set(path);
  }

  $: mainItems = navItems.filter(item => !item.bottom);
  $: bottomItems = navItems.filter(item => item.bottom);
</script>

<!-- Nav Header (logo area) — YashAdmin .nav-header -->
<div class="nav-header" class:collapsed={!$sidebarOpen}>
  <a href="#/" class="brand-logo" on:click|preventDefault={() => navigate('/')}>
    {#if $sidebarOpen}
      <img src={eskLogoB} alt="ESK-IT" class="logo-wide" />
    {:else}
      <img src={logoUrl} alt="Logo" class="logo-icon" />
    {/if}
  </a>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="nav-control" on:click={() => sidebarOpen.update(v => !v)}>
    {#if $sidebarOpen}
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>
    {:else}
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg>
    {/if}
  </div>
</div>

<!-- Sidebar (deznav) — YashAdmin .deznav -->
<div class="deznav" class:collapsed={!$sidebarOpen}>
  <div class="deznav-scroll">
    <ul class="metismenu">
      {#each mainItems as item}
        {#if item.type === 'section'}
          {#if $sidebarOpen}
            <li class="menu-title">{item.label}</li>
          {:else}
            <li class="menu-title-dot"></li>
          {/if}
        {:else}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <li
            class:mm-active={$currentPage === item.path}
            on:click={() => navigate(item.path)}
          >
            <a href="#/{item.key}" on:click|preventDefault>
              <div class="menu-icon">
                {#if iconMap[item.icon]}
                  <svelte:component this={iconMap[item.icon]} size={22} strokeWidth={1.5} />
                {:else}
                  <span class="nav-emoji">{item.emoji}</span>
                {/if}
              </div>
              {#if $sidebarOpen}
                <span class="nav-text">{item.label}</span>
              {/if}
              {#if item.key === 'tasks' && overdueCount > 0}
                <span class="badge-count">{overdueCount}</span>
              {/if}
            </a>
          </li>
        {/if}
      {/each}
    </ul>

    <!-- Bottom items -->
    <div class="nav-bottom-section">
      {#each bottomItems as item}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          class="nav-bottom-item"
          class:mm-active={$currentPage === item.path}
          on:click={() => navigate(item.path)}
        >
          <div class="menu-icon">
            {#if iconMap[item.icon]}
              <svelte:component this={iconMap[item.icon]} size={20} strokeWidth={1.5} />
            {/if}
          </div>
          {#if $sidebarOpen}
            <span class="nav-text">{item.label}</span>
          {/if}
        </div>
      {/each}
      {#if $sidebarOpen}
        <div class="version-text">v{appVersion}</div>
      {/if}
    </div>
  </div>
</div>

<style>
  /* ═══════════════════════════════════════
     NAV HEADER — Logo area (YashAdmin exact)
     Height: 4.375rem (70px), Width: 15rem (240px)
     ═══════════════════════════════════════ */
  .nav-header {
    position: fixed;
    top: 0;
    left: 0;
    width: var(--sidebar-width);
    height: var(--header-height);
    display: flex;
    align-items: center;
    justify-content: space-between;
    background-color: var(--bg-sidebar);
    z-index: 7;
    transition: all 0.2s ease;
    padding: 0 0.5rem 0 1.1rem;
    border-bottom: 1px solid var(--border-subtle);
    border-right: 1px solid var(--border-subtle);
  }

  .nav-header.collapsed {
    width: var(--sidebar-width-collapsed);
  }

  .brand-logo {
    display: flex;
    align-items: center;
    gap: 0.6375rem;
    text-decoration: none;
    overflow: hidden;
  }

  .logo-icon {
    width: 2.2rem;
    height: 2.2rem;
    object-fit: contain;
    flex-shrink: 0;
    border-radius: 0.5rem;
  }

  .logo-wide {
    max-width: 190px;
    max-height: 44px;
    object-fit: contain;
    padding: 0.125rem 0;
  }

  .brand-title {
    font-size: 1.375rem;
    font-weight: 700;
    color: var(--text-heading);
    white-space: nowrap;
    letter-spacing: -0.3px;
  }

  /* ── YashAdmin collapse toggle — square with rounded corners at sidebar edge ── */
  .nav-control {
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 0.5rem;
    background: var(--primary);
    color: #fff;
    transition: all 0.2s ease;
    flex-shrink: 0;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    border: none;
  }

  .nav-control:hover {
    background: var(--primary-hover);
    transform: scale(1.05);
  }

  /* ═══════════════════════════════════════
     DEZNAV — Sidebar (YashAdmin exact)
     Width: 15rem (240px)
     Top: 4.375rem (70px, below nav-header)
     ═══════════════════════════════════════ */
  .deznav {
    position: fixed;
    top: var(--header-height);
    left: 0;
    width: var(--sidebar-width);
    height: calc(100vh - var(--header-height));
    background-color: var(--bg-sidebar);
    border-right: 1px solid var(--border-subtle);
    z-index: 6;
    transition: all 0.2s ease;
    box-shadow: 0rem 0.9375rem 1.875rem 0rem rgba(0, 0, 0, 0.02);
    overflow: hidden;
  }

  .deznav.collapsed {
    width: var(--sidebar-width-collapsed);
  }

  .deznav-scroll {
    height: 100%;
    overflow-y: auto;
    overflow-x: hidden;
    padding-top: 1rem;
    display: flex;
    flex-direction: column;
  }

  /* ═══════════════════════════════════════
     METISMENU — Nav items (YashAdmin exact)
     ═══════════════════════════════════════ */
  .metismenu {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    flex: 1;
  }

  /* Section titles */
  .menu-title {
    margin: 0.625rem 1.875rem 0;
    padding: 1.5625rem 0 0.625rem;
    text-transform: uppercase;
    font-size: 0.75rem;
    letter-spacing: 0.05rem;
    border-top: 1px solid var(--border-subtle);
    color: #999999;
    user-select: none;
  }

  .menu-title:first-child {
    border-top: none;
    margin-top: 0;
    padding-top: 0;
  }

  .menu-title-dot {
    height: 1px;
    background: var(--border-subtle);
    margin: 0.75rem 1rem;
  }

  /* Nav items */
  .metismenu li:not(.menu-title):not(.menu-title-dot) {
    position: relative;
  }

  .metismenu li a {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.75rem 1.875rem;
    font-size: 0.9375rem;
    font-weight: 400;
    color: var(--text-secondary);
    text-decoration: none;
    transition: all 0.2s ease;
    cursor: pointer;
    position: relative;
    white-space: nowrap;
    overflow: hidden;
  }

  .metismenu li a:hover {
    color: var(--secondary);
  }

  .metismenu li a:hover .menu-icon :global(svg) {
    color: var(--secondary);
  }

  /* Active state — YashAdmin uses secondary (gold #F8B940) */
  .metismenu li.mm-active > a {
    color: var(--secondary);
    font-weight: 500;
  }

  .metismenu li.mm-active > a .menu-icon :global(svg) {
    color: var(--secondary);
    stroke: var(--secondary);
  }

  /* Menu icon container */
  .menu-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.5rem;
    height: 1.5rem;
    flex-shrink: 0;
  }

  .menu-icon :global(svg) {
    color: #96A0AF;
    transition: color 0.2s ease;
  }

  .nav-emoji {
    font-size: 1.125rem;
    line-height: 1;
  }

  .nav-text {
    font-size: 0.9375rem;
    line-height: 1;
  }

  /* Overdue badge */
  .badge-count {
    position: absolute;
    top: 0.5rem;
    right: 1rem;
    background: var(--danger);
    color: #fff;
    font-size: 0.625rem;
    font-weight: 700;
    min-width: 1.125rem;
    height: 1.125rem;
    border-radius: 0.5625rem;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 0.25rem;
  }

  /* ═══════════════════════════════════════
     BOTTOM SECTION
     ═══════════════════════════════════════ */
  .nav-bottom-section {
    margin-top: auto;
    padding: 0.5rem 0 1rem;
    border-top: 1px solid var(--border-subtle);
  }

  .nav-bottom-item {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.625rem 1.875rem;
    font-size: 0.9375rem;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
    overflow: hidden;
  }

  .nav-bottom-item:hover {
    color: var(--secondary);
  }

  .nav-bottom-item:hover .menu-icon :global(svg) {
    color: var(--secondary);
  }

  .nav-bottom-item.mm-active {
    color: var(--secondary);
  }

  .nav-bottom-item.mm-active .menu-icon :global(svg) {
    color: var(--secondary);
    stroke: var(--secondary);
  }

  .version-text {
    text-align: center;
    font-size: 0.6875rem;
    color: var(--text-muted);
    padding: 0.5rem 0 0;
  }

  /* ═══════════════════════════════════════
     COLLAPSED STATE
     ═══════════════════════════════════════ */
  .collapsed .metismenu li a {
    padding: 0.75rem 0;
    justify-content: center;
  }

  .collapsed .nav-bottom-item {
    padding: 0.625rem 0;
    justify-content: center;
  }
</style>
