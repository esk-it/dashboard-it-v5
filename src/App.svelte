<script>
  import { onMount } from 'svelte';
  import { currentPage, sidebarOpen } from './lib/stores/navigation.js';
  import { loadSettings } from './lib/stores/settings.js';
  import { isAuthenticated, checkAuth, logout } from './lib/stores/auth.js';
  import SplashScreen from './lib/components/SplashScreen.svelte';
  import Sidebar from './lib/components/Sidebar.svelte';
  import Navbar from './lib/components/Navbar.svelte';
  import Toast from './lib/components/Toast.svelte';
  import SearchPalette from './lib/components/SearchPalette.svelte';
  import QuickCreate from './lib/components/QuickCreate.svelte';
  import LoginPage from './lib/pages/LoginPage.svelte';
  import LockScreenPage from './lib/pages/LockScreenPage.svelte';
  import HomePage from './lib/pages/HomePage.svelte';
  import PlaceholderPage from './lib/pages/PlaceholderPage.svelte';
  import PlanningPage from './lib/pages/PlanningPage.svelte';
  import TasksPage from './lib/pages/TasksPage.svelte';
  import DocumentsPage from './lib/pages/DocumentsPage.svelte';
  import EmailPage from './lib/pages/EmailPage.svelte';
  import NewsPage from './lib/pages/NewsPage.svelte';
  import ChangelogPage from './lib/pages/ChangelogPage.svelte';
  import WikiPage from './lib/pages/WikiPage.svelte';
  import SuppliersPage from './lib/pages/SuppliersPage.svelte';
  import ParcPage from './lib/pages/ParcPage.svelte';
  import SecurityPage from './lib/pages/SecurityPage.svelte';
  import MonitoringPage from './lib/pages/MonitoringPage.svelte';
  import LauncherPage from './lib/pages/LauncherPage.svelte';
  import ToolsPage from './lib/pages/ToolsPage.svelte';
  import UsersPage from './lib/pages/UsersPage.svelte';
  import SettingsPage from './lib/pages/SettingsPage.svelte';

  let showSearch = false;
  let showQuickCreate = false;
  let splashDone = false;

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
    // Check if user is authenticated, redirect to login if not
    const authed = await checkAuth();
    if (!authed) currentPage.set('/login');

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
    {:else if $currentPage === '/planning'}
      <PlanningPage />
    {:else if $currentPage === '/tasks'}
      <TasksPage />
    {:else if $currentPage === '/documents'}
      <DocumentsPage />
    {:else if $currentPage === '/email'}
      <EmailPage />
    {:else if $currentPage === '/suppliers'}
      <SuppliersPage />
    {:else if $currentPage === '/parc'}
      <ParcPage />
    {:else if $currentPage === '/security'}
      <SecurityPage />
    {:else if $currentPage === '/wiki'}
      <WikiPage />
    {:else if $currentPage === '/changelog'}
      <ChangelogPage />
    {:else if $currentPage === '/monitoring'}
      <MonitoringPage />
    {:else if $currentPage === '/launcher'}
      <LauncherPage />
    {:else if $currentPage === '/tools'}
      <ToolsPage />
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

  {#if showSearch}
    <SearchPalette on:close={() => showSearch = false} />
  {/if}
  {#if showQuickCreate}
    <QuickCreate on:close={() => showQuickCreate = false} />
  {/if}
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
</style>
