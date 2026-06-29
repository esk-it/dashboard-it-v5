<script>
  import { onMount } from 'svelte';
  import { currentPage, sidebarOpen, navItems, whatsNew, seenNewKeys } from './lib/stores/navigation.js';
  import { loadSettings } from './lib/stores/settings.js';
  import { loadEstablishments } from './lib/stores/establishments.js';
  import { isAuthenticated, checkAuth, logout } from './lib/stores/auth.js';
  import { isOnline, startHealthPolling, recheckNow } from './lib/stores/health.js';
  import SplashScreen from './lib/components/SplashScreen.svelte';
  import Sidebar from './lib/components/Sidebar.svelte';
  import Navbar from './lib/components/Navbar.svelte';
  import Toast from './lib/components/Toast.svelte';
  import SearchPalette from './lib/components/SearchPalette.svelte';
  import QuickCreate from './lib/components/QuickCreate.svelte';
  import WhatsNewModal from './lib/components/WhatsNewModal.svelte';
  import LoginPage from './lib/pages/LoginPage.svelte';
  import LockScreenPage from './lib/pages/LockScreenPage.svelte';
  import ChangePasswordPage from './lib/pages/ChangePasswordPage.svelte';
  import HomePage from './lib/pages/HomePage.svelte';
  import PlaceholderPage from './lib/pages/PlaceholderPage.svelte';
  // v7.6.0 — Modules désactivés (PlanningPage, EmailPage, ChangelogPage,
  // ToolsPage). Fichiers conservés sur disque pour réactivation facile
  // (un revert de cet import + route suffit).
  import TasksPage from './lib/pages/TasksPage.svelte';
  import ProjectsPage from './lib/pages/ProjectsPage.svelte';
  import DossiersPage from './lib/pages/DossiersPage.svelte';
  import NewsPage from './lib/pages/NewsPage.svelte';
  import WikiPage from './lib/pages/WikiPage.svelte';
  import SuppliersPage from './lib/pages/SuppliersPage.svelte';
  import ParcPage from './lib/pages/ParcPage.svelte';
  import ChromebooksPage from './lib/pages/ChromebooksPage.svelte';
  import SecurityPage from './lib/pages/SecurityPage.svelte';
  import MonitoringPage from './lib/pages/MonitoringPage.svelte';
  import LauncherPage from './lib/pages/LauncherPage.svelte';
  import UsersPage from './lib/pages/UsersPage.svelte';
  import SettingsPage from './lib/pages/SettingsPage.svelte';

  let showSearch = false;
  let showQuickCreate = false;
  let splashDone = false;
  let recheckingHealth = false;

  // "What's new" modal: shows once per (module, version) when the user first
  // navigates to a module that has unread highlights. Closing the modal marks
  // it as seen and removes the NEW badge in the sidebar.
  let whatsNewKey = null;
  $: {
    // React to currentPage changes after the splash. Only triggers if the
    // current page maps to a known nav item that has whatsNew content the
    // user hasn't acknowledged yet.
    if (splashDone) {
      const item = navItems.find(i => i.path === $currentPage);
      if (item && whatsNew[item.key] && !$seenNewKeys.has(item.key) && whatsNewKey !== item.key) {
        whatsNewKey = item.key;
      }
    }
  }

  async function retryBackend() {
    recheckingHealth = true;
    await recheckNow();
    recheckingHealth = false;
  }

  $: if (splashDone) loadSettings();

  function handleBeforeUnload(e) {
    const hasOpenDialog = document.querySelector('.dialog-overlay, .modal-overlay');
    if (hasOpenDialog) {
      e.preventDefault();
      e.returnValue = '';
    }
  }

  onMount(async () => {
    loadSettings();
    loadEstablishments();
    startHealthPolling();
    // Check "remember me" — if active and not expired, skip login
    const rememberUntil = parseInt(localStorage.getItem('auth_remember_until') || '0');
    const hasToken = !!localStorage.getItem('auth_token');
    if (rememberUntil > Date.now() && hasToken) {
      // Session still valid — check auth and proceed
      const authed = await checkAuth();
      if (!authed) { logout(); currentPage.set('/login'); }
    } else {
      // Expired or not remembered — force login
      logout();
      currentPage.set('/login');
    }

    function handleKeydown(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        showSearch = !showSearch;
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        e.preventDefault();
        showQuickCreate = !showQuickCreate;
      }
    }

    window.addEventListener('keydown', handleKeydown);
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('keydown', handleKeydown);
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  });
</script>

<SplashScreen on:done={() => splashDone = true} />

{#if splashDone}
  {#if $currentPage === '/login'}
    <LoginPage />
  {:else if $currentPage === '/change-password'}
    <ChangePasswordPage />
  {:else if $currentPage === '/lock'}
    <LockScreenPage />
  {:else}
  <!-- YashAdmin layout: nav-header + sidebar (in Sidebar component), header on top, content-body below -->
  <Sidebar />
  <Navbar on:search={() => showSearch = !showSearch} on:lock={() => currentPage.set('/lock')} />

  <div class="content-body" class:sidebar-collapsed={!$sidebarOpen}>
    {#key $currentPage}
    <div class="page-transition">
    {#if $currentPage === '/'}
      <HomePage />
    {:else if $currentPage === '/news'}
      <NewsPage />
    {:else if $currentPage === '/tasks'}
      <TasksPage />
    {:else if $currentPage === '/projects'}
      <ProjectsPage />
    {:else if $currentPage === '/documents'}
      <DossiersPage />
    {:else if $currentPage === '/suppliers'}
      <SuppliersPage />
    {:else if $currentPage === '/parc'}
      <ParcPage />
    {:else if $currentPage === '/chromebooks'}
      <ChromebooksPage />
    {:else if $currentPage === '/security'}
      <SecurityPage />
    {:else if $currentPage === '/wiki'}
      <WikiPage />
    {:else if $currentPage === '/monitoring'}
      <MonitoringPage />
    {:else if $currentPage === '/launcher'}
      <LauncherPage />
    {:else if $currentPage === '/users'}
      <UsersPage />
    {:else if $currentPage === '/settings'}
      <SettingsPage />
    {:else}
      <PlaceholderPage title="Page introuvable" emoji={'\u{1F50D}'} />
    {/if}
    </div>
    {/key}
  </div>

  <Toast />

  {#if !$isOnline}
    <div class="backend-offline-banner">
      <span class="bo-icon">{'\u26A0\uFE0F'}</span>
      <span class="bo-text">
        <strong>Backend déconnecté</strong> — l'app ne peut plus charger ni sauvegarder de données.
        Si le problème persiste, redémarre l'application.
      </span>
      <button class="bo-btn" on:click={retryBackend} disabled={recheckingHealth}>
        {recheckingHealth ? 'Vérification…' : 'Réessayer'}
      </button>
    </div>
  {/if}

  {#if showSearch}
    <SearchPalette on:close={() => showSearch = false} />
  {/if}
  {#if showQuickCreate}
    <QuickCreate on:close={() => showQuickCreate = false} />
  {/if}

  <WhatsNewModal bind:activeKey={whatsNewKey} />
  {/if}
{/if}

<style>
  /* ═══════════════════════════════════════
     CONTENT BODY — YashAdmin exact
     margin-left: 15rem (240px) = sidebar width
     margin-top: 4.375rem (70px) = header height
     ═══════════════════════════════════════ */
  .content-body {
    position: fixed;
    top: var(--header-height);
    left: var(--sidebar-width);
    right: 0;
    bottom: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 1.875rem;
    transition: left 0.2s ease;
    background: var(--bg-base);
  }

  .content-body.sidebar-collapsed {
    left: var(--sidebar-width-collapsed);
  }


  .page-transition {
    animation: pageIn 0.25s ease-out;
  }


  @keyframes pageIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Backend-down banner — fixed at the bottom so it never hides primary content */
  .backend-offline-banner {
    position: fixed; left: 50%; bottom: 16px; transform: translateX(-50%);
    z-index: 9998;
    display: flex; align-items: center; gap: 12px;
    padding: 10px 16px;
    background: rgba(239, 68, 68, 0.95);
    color: #fff;
    border-radius: 10px;
    box-shadow: 0 8px 24px rgba(239, 68, 68, 0.35);
    max-width: 720px; font-size: 13px;
  }
  .bo-icon { font-size: 18px; }
  .bo-text { flex: 1; line-height: 1.4; }
  .bo-text strong { font-weight: 700; }
  .bo-btn {
    background: rgba(255,255,255,0.18); color: #fff;
    border: 1px solid rgba(255,255,255,0.35);
    padding: 6px 12px; border-radius: 6px; font-weight: 600; cursor: pointer;
    font-size: 12px; white-space: nowrap;
  }
  .bo-btn:hover:not(:disabled) { background: rgba(255,255,255,0.28); }
  .bo-btn:disabled { opacity: 0.6; cursor: wait; }
</style>
