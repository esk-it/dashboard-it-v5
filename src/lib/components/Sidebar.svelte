<script>
  import { onMount, onDestroy } from 'svelte';
  import { currentPage, navItems, sidebarOpen } from '../stores/navigation.js';
  import { theme } from '../stores/theme.js';
  import {
    Home, Globe, Calendar, CheckSquare, FileText, Users, Monitor,
    Shield, BookOpen, ClipboardList, Activity, Rocket, Wrench, Settings,
    MessageSquare, Mail, Users2, ChevronLeft, ChevronRight
  } from 'lucide-svelte';

  const iconMap = { Home, Globe, Calendar, CheckSquare, FileText, Users, Monitor, Shield, BookOpen, ClipboardList, Activity, Rocket, Wrench, Settings, MessageSquare, Mail, Users2 };

  let appVersion = '';
  let overdueCount = 0;
  let interval;

  onMount(async () => {
    try {
      const { getVersion } = await import('@tauri-apps/api/app');
      appVersion = await getVersion();
    } catch {
      appVersion = '5.0.1';
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

  function toggleSidebar() {
    sidebarOpen.update(v => !v);
  }

  $: mainItems = navItems.filter(item => !item.bottom);
  $: bottomItems = navItems.filter(item => item.bottom);
</script>

<aside class="sidebar" class:collapsed={!$sidebarOpen}>
  <!-- Brand / Logo area -->
  <div class="brand">
    {#if $sidebarOpen}
      <span class="brand-text">ITManager</span>
    {:else}
      <span class="brand-text-short">IT</span>
    {/if}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <button class="toggle-btn" on:click={toggleSidebar} aria-label="Toggle sidebar">
      {#if $sidebarOpen}
        <ChevronLeft size={18} />
      {:else}
        <ChevronRight size={18} />
      {/if}
    </button>
  </div>

  <!-- Main navigation -->
  <nav class="nav-main">
    {#each mainItems as item}
      {#if item.type === 'section'}
        {#if $sidebarOpen}
          <div class="section-header">{item.label}</div>
        {:else}
          <div class="section-divider"></div>
        {/if}
      {:else}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          class="nav-item"
          class:active={$currentPage === item.path}
          title={!$sidebarOpen ? item.label : ''}
          on:click={() => navigate(item.path)}
        >
          <span class="nav-icon">
            {#if iconMap[item.icon]}
              <svelte:component this={iconMap[item.icon]} size={20} />
            {/if}
          </span>
          {#if $sidebarOpen}
            <span class="nav-label">{item.label}</span>
          {/if}
          {#if item.key === 'tasks' && overdueCount > 0}
            <span class="overdue-badge">{overdueCount}</span>
          {/if}
        </div>
      {/if}
    {/each}
  </nav>

  <!-- Bottom navigation -->
  <nav class="nav-bottom">
    {#each bottomItems as item}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        class="nav-item"
        class:active={$currentPage === item.path}
        title={!$sidebarOpen ? item.label : ''}
        on:click={() => navigate(item.path)}
      >
        <span class="nav-icon">
          {#if iconMap[item.icon]}
            <svelte:component this={iconMap[item.icon]} size={20} />
          {/if}
        </span>
        {#if $sidebarOpen}
          <span class="nav-label">{item.label}</span>
        {/if}
      </div>
    {/each}

    <!-- Version -->
    <div class="version">
      {#if $sidebarOpen}
        <span>v{appVersion}</span>
      {:else}
        <span class="version-dot"></span>
      {/if}
    </div>
  </nav>
</aside>

<style>
  .sidebar {
    width: 250px;
    min-width: 250px;
    height: 100vh;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    z-index: 100;
    user-select: none;
    overflow: hidden;
    transition: width 250ms ease, min-width 250ms ease;
    position: fixed;
    top: 0;
    left: 0;
  }

  .sidebar.collapsed {
    width: 75px;
    min-width: 75px;
  }

  /* Brand */
  .brand {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    height: 60px;
    min-height: 60px;
    border-bottom: 1px solid var(--border-subtle);
    white-space: nowrap;
    overflow: hidden;
  }

  .brand-text {
    font-family: 'Poppins', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: var(--primary);
    letter-spacing: -0.5px;
  }

  .brand-text-short {
    font-family: 'Poppins', sans-serif;
    font-size: 18px;
    font-weight: 700;
    color: var(--primary);
    margin: 0 auto;
  }

  .toggle-btn {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s ease, color 0.15s ease;
    flex-shrink: 0;
  }

  .toggle-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .collapsed .toggle-btn {
    position: absolute;
    right: 50%;
    transform: translateX(50%);
    top: 18px;
  }

  .collapsed .brand {
    justify-content: center;
  }

  /* Navigation */
  .nav-main {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 8px;
  }

  .nav-bottom {
    margin-top: auto;
    padding: 8px;
    border-top: 1px solid var(--border-subtle);
  }

  /* Section headers */
  .section-header {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 16px 12px 6px;
    white-space: nowrap;
    overflow: hidden;
  }

  .section-divider {
    height: 1px;
    background: var(--border-subtle);
    margin: 8px 12px;
  }

  /* Nav item */
  .nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    margin: 2px 0;
    border-radius: 8px;
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    transition: background 0.15s ease;
    position: relative;
    color: var(--text-secondary);
  }

  .nav-item:hover {
    background: var(--bg-hover);
  }

  .nav-item.active {
    background: rgba(var(--primary-rgb), 0.1);
    border-left: 3px solid var(--primary);
    padding-left: 9px;
  }

  .nav-item.active .nav-icon {
    color: var(--primary);
  }

  .nav-item.active .nav-label {
    color: var(--primary);
    font-weight: 500;
  }

  .nav-icon {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
  }

  .nav-label {
    font-family: 'Poppins', sans-serif;
    font-size: 13.5px;
    color: var(--text-secondary);
    transition: opacity 0.15s ease;
  }

  .collapsed .nav-item {
    justify-content: center;
    padding: 10px;
    gap: 0;
  }

  .collapsed .nav-item.active {
    padding-left: 7px;
  }

  /* Overdue badge */
  .overdue-badge {
    position: absolute;
    top: 4px;
    right: 4px;
    background: #EF4444;
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    min-width: 18px;
    height: 18px;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 4px;
    box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
    animation: badgePulse 2s ease-in-out infinite;
  }

  @keyframes badgePulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.1); }
  }

  /* Version */
  .version {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 10px 0 4px;
    font-size: 11px;
    color: var(--text-muted);
  }

  .version-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--text-muted);
    opacity: 0.5;
  }

  /* Scrollbar */
  .nav-main::-webkit-scrollbar {
    width: 4px;
  }

  .nav-main::-webkit-scrollbar-track {
    background: transparent;
  }

  .nav-main::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb);
    border-radius: 4px;
  }

  .nav-main::-webkit-scrollbar-thumb:hover {
    background: var(--scrollbar-thumb-hover);
  }
</style>
