<script>
  import { onMount, onDestroy } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import { currentPage, navItems, navCategories, sidebarOpen, seenNewKeys, isNew } from '../stores/navigation.js';
  import { Home, Globe, Calendar, CheckSquare, FileText, Mail, Users, Monitor, Shield, BookOpen, ClipboardList, Activity, Rocket, Wrench, Settings, Target } from 'lucide-svelte';
  import { API_BASE } from '../api/client.js';
  import logoUrl from '../../assets/logo.png';
  import nomB from '../../assets/nomB.png';

  const dispatch = createEventDispatcher();
  const iconMap = { Home, Globe, Calendar, CheckSquare, FileText, Mail, Users, Monitor, Shield, BookOpen, ClipboardList, Activity, Rocket, Wrench, Settings, Target };

  // Top-level items (no `category`) and items grouped by category. Computed once
  // since the navItems list is static.
  const topLevelItems = navItems.filter(i => !i.category);
  const itemsByCategory = navCategories.reduce((acc, cat) => {
    acc[cat.key] = navItems.filter(i => i.category === cat.key);
    return acc;
  }, {});

  // Numeric badges fed from real backend state — refreshed every 30s.
  let appVersion = '';
  let overdueCount = 0;
  let unreadMailCount = 0;
  let interval;

  onMount(async () => {
    try {
      const { getVersion } = await import('@tauri-apps/api/app');
      appVersion = await getVersion();
    } catch {
      appVersion = '4.0.1';
    }
    loadBadges();
    interval = setInterval(loadBadges, 30000);
  });

  onDestroy(() => { if (interval) clearInterval(interval); });

  async function loadBadges() {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/kpis`);
      const data = await res.json();
      overdueCount = data.overdue_tasks || 0;
    } catch { /* ignore */ }
    try {
      const res = await fetch(`${API_BASE}/api/gmail/unread-count`);
      const data = await res.json();
      unreadMailCount = data.count || 0;
    } catch { /* ignore */ }
  }

  function badgeFor(key) {
    if (key === 'tasks' && overdueCount > 0) return { value: overdueCount, kind: 'danger' };
    if (key === 'email' && unreadMailCount > 0) return { value: unreadMailCount > 99 ? '99+' : unreadMailCount, kind: 'mail' };
    return null;
  }

  function navigate(path) {
    currentPage.set(path);
  }
</script>

{#snippet navItem(item)}
  {@const badge = badgeFor(item.key)}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <li class:mm-active={$currentPage === item.path} on:click={() => navigate(item.path)}>
    <a href="#/{item.key}" on:click|preventDefault title={!$sidebarOpen ? item.label : undefined}>
      <div class="menu-icon">
        {#if iconMap[item.icon]}
          <svelte:component this={iconMap[item.icon]} size={20} strokeWidth={1.5} />
        {:else}
          <span class="nav-emoji">{item.emoji}</span>
        {/if}
      </div>
      {#if $sidebarOpen}
        <span class="nav-text">{item.label}</span>
      {/if}
      {#if badge}
        <span class="badge-count" class:badge-mail={badge.kind === 'mail'}>{badge.value}</span>
      {/if}
      {#if isNew(item.key, $seenNewKeys) && $sidebarOpen}
        <span class="badge-new">NEW</span>
      {/if}
    </a>
  </li>
{/snippet}

<!-- Nav Header (logo area) -->
<div class="nav-header" class:collapsed={!$sidebarOpen}>
  <a href="#/" class="brand-logo" on:click|preventDefault={() => navigate('/')}>
    <img src={logoUrl} alt="Logo" class="logo-icon" />
    {#if $sidebarOpen}
      <img src={nomB} alt="Le Kreisker" class="brand-name-img" />
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

<!-- Sidebar (deznav) — YashAdmin-style: section labels (decorative) + flat items -->
<div class="deznav" class:collapsed={!$sidebarOpen}>
  <div class="deznav-scroll">
    <ul class="metismenu">
      <!-- Top-level items (no section label above) -->
      {#each topLevelItems as item}
        {@render navItem(item)}
      {/each}

      <!-- Categories: section label + flat items underneath -->
      {#each navCategories as cat}
        {@const items = itemsByCategory[cat.key] || []}
        {#if items.length > 0}
          {#if $sidebarOpen}
            <li class="category-label">{cat.label}</li>
          {/if}
          {#each items as item}
            {@render navItem(item)}
          {/each}
        {/if}
      {/each}
    </ul>

    {#if $sidebarOpen}
      <div class="version-text">v{appVersion}</div>
    {/if}
  </div>
</div>

<style>
  /* ═══════════════════════════════════════
     NAV HEADER
     ═══════════════════════════════════════ */
  .nav-header {
    position: fixed;
    top: 0; left: 0;
    width: var(--sidebar-width);
    height: var(--header-height);
    display: flex; align-items: center; justify-content: space-between;
    background-color: var(--bg-sidebar);
    z-index: 7;
    transition: all 0.2s ease;
    padding: 0 0.5rem 0 1.1rem;
    border-bottom: 1px solid var(--border-subtle);
    border-right: 1px solid var(--border-subtle);
  }
  .nav-header.collapsed { width: var(--sidebar-width-collapsed); }
  .brand-logo { display: flex; align-items: center; gap: 0.6375rem; text-decoration: none; overflow: hidden; }
  .logo-icon { width: 2.2rem; height: 2.2rem; object-fit: contain; flex-shrink: 0; border-radius: 0.5rem; }
  .brand-name-img { max-height: 46px; object-fit: contain; margin-left: 0.75rem; }

  .nav-control {
    cursor: pointer; display: flex; align-items: center; justify-content: center;
    width: 2rem; height: 2rem; border-radius: 0.5rem;
    background: var(--primary); color: #fff;
    transition: all 0.2s ease; flex-shrink: 0;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2); border: none;
  }
  .nav-control:hover { background: var(--primary-hover); transform: scale(1.05); }

  /* ═══════════════════════════════════════
     SIDEBAR
     ═══════════════════════════════════════ */
  .deznav {
    position: fixed;
    top: var(--header-height); left: 0;
    width: var(--sidebar-width);
    height: calc(100vh - var(--header-height));
    background-color: var(--bg-sidebar);
    border-right: 1px solid var(--border-subtle);
    z-index: 6;
    transition: all 0.2s ease;
    box-shadow: 0rem 0.9375rem 1.875rem 0rem rgba(0, 0, 0, 0.02);
    overflow: hidden;
  }
  .deznav.collapsed { width: var(--sidebar-width-collapsed); }
  .deznav-scroll {
    height: 100%; overflow-y: auto; overflow-x: hidden;
    padding-top: 0.75rem;
    display: flex; flex-direction: column;
  }

  .metismenu {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column;
    flex: 1;
  }

  /* ── Nav items (top-level + items inside a section) ───────── */
  .metismenu li:not(.category-label) { position: relative; }
  .metismenu li:not(.category-label) a {
    display: flex; align-items: center; gap: 0.75rem;
    padding: 0.625rem 1.5rem;
    font-size: 0.9375rem; font-weight: 400;
    color: var(--text-secondary);
    text-decoration: none;
    transition: color 0.15s ease, background 0.15s ease;
    cursor: pointer; position: relative;
    white-space: nowrap; overflow: hidden;
  }
  .metismenu li:not(.category-label) a:hover { color: var(--secondary); }
  .metismenu li:not(.category-label) a:hover .menu-icon :global(svg) { color: var(--secondary); }

  .metismenu li.mm-active > a {
    color: var(--secondary); font-weight: 500;
  }
  .metismenu li.mm-active > a .menu-icon :global(svg) {
    color: var(--secondary); stroke: var(--secondary);
  }

  .menu-icon {
    display: flex; align-items: center; justify-content: center;
    width: 1.5rem; height: 1.5rem; flex-shrink: 0;
  }
  .menu-icon :global(svg) { color: #96A0AF; transition: color 0.2s ease; }
  .nav-emoji { font-size: 1.125rem; line-height: 1; }
  .nav-text { font-size: 0.9375rem; line-height: 1; }

  /* ── Section label (YashAdmin-style: pure visual divider, not interactive) ─ */
  .category-label {
    padding: 1.25rem 1.5rem 0.5rem;
    font-size: 0.6875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6B7280;
    user-select: none;
    line-height: 1;
  }

  /* ── Badges ───────────────────────────────────────────────── */
  .badge-count {
    margin-left: auto;
    background: var(--danger); color: #fff;
    font-size: 0.625rem; font-weight: 700;
    min-width: 1.125rem; height: 1.125rem; border-radius: 0.5625rem;
    display: flex; align-items: center; justify-content: center;
    padding: 0 0.375rem; flex-shrink: 0;
  }
  .badge-mail { background: #3B82F6; }
  .badge-new {
    margin-left: 6px;
    background: #EF4444; color: #fff;
    font-size: 0.5625rem; font-weight: 700; letter-spacing: 0.05em;
    padding: 1px 5px; border-radius: 3px;
    flex-shrink: 0;
  }

  /* ── Version footer ───────────────────────────────────────── */
  .version-text {
    text-align: center; font-size: 0.6875rem;
    color: var(--text-muted);
    padding: 0.75rem 0 1rem;
    margin-top: auto;
    border-top: 1px solid var(--border-subtle);
  }

  /* ═══════════════════════════════════════
     COLLAPSED MODE — flat icons, no labels, no section headers
     ═══════════════════════════════════════ */
  .collapsed .metismenu li:not(.category-label) a {
    padding: 0.625rem 0;
    justify-content: center;
  }
  .collapsed .badge-count {
    position: absolute;
    top: 0.25rem; right: 0.5rem;
    margin-left: 0;
  }
</style>
