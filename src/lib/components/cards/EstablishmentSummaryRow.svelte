<script>
  // Per-establishment KPI cards (one card per school, displayed in a 3-column
  // row on the Home page). Aggregates open tasks, overdue tasks, in-progress
  // projects and this-week events for each establishment.
  //
  // Strategy: fetch tasks/projects/events ONCE, group by `site` in JS. This is
  // faster + less code than 9 parallel endpoint calls (3 establishments × 3
  // sources). Refreshed every 5 min from HomePage.

  import { onMount } from 'svelte';
  import { api } from '../../api/client.js';
  import { currentPage } from '../../stores/navigation.js';
  import { establishments, logoUrl } from '../../stores/establishments.js';

  let tasksByCode = {};
  let overdueByCode = {};
  let projectsByCode = {};
  let eventsByCode = {};
  let loaded = false;

  export function refresh() { fetchAll(); }

  onMount(() => fetchAll());

  function fmtDate(d) {
    return d.toISOString().slice(0, 10);
  }

  async function fetchAll() {
    try {
      const today = new Date();
      const todayStr = fmtDate(today);
      const weekEnd = new Date(today.getTime() + 7 * 86400000);
      const weekStr = fmtDate(weekEnd);

      const [tasks, projects, events] = await Promise.all([
        api.get('/api/tasks?status=open').catch(() => []),
        api.get('/api/projects').catch(() => []),
        api.get(`/api/planning/events?start=${todayStr}&end=${weekStr}`).catch(() => []),
      ]);

      // Reset
      tasksByCode = {};
      overdueByCode = {};
      projectsByCode = {};
      eventsByCode = {};

      for (const t of (tasks || [])) {
        const code = t.site || '__none__';
        tasksByCode[code] = (tasksByCode[code] || 0) + 1;
        if (t.due_date && t.due_date < todayStr) {
          overdueByCode[code] = (overdueByCode[code] || 0) + 1;
        }
      }
      for (const p of (projects || [])) {
        if (p.status !== 'in_progress') continue;
        const code = p.site || '__none__';
        projectsByCode[code] = (projectsByCode[code] || 0) + 1;
      }
      for (const e of (events || [])) {
        const code = e.site || '__none__';
        eventsByCode[code] = (eventsByCode[code] || 0) + 1;
      }
    } catch {
      /* leave previous values */
    } finally {
      loaded = true;
    }
  }

  // Clicking a card jumps to the Tasks module filtered on this site. Done via
  // sessionStorage so the page can pick the filter up on mount (no router
  // params in this app yet — same pattern used elsewhere).
  function openSite(code) {
    try { sessionStorage.setItem('tasks.filterSite', code); } catch {}
    currentPage.set('/tasks');
  }
</script>

<div class="es-row">
  {#each $establishments as e (e.id)}
    {@const tasks = tasksByCode[e.code] || 0}
    {@const overdue = overdueByCode[e.code] || 0}
    {@const projects = projectsByCode[e.code] || 0}
    {@const events = eventsByCode[e.code] || 0}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <article class="es-card" style="--accent: {e.color}" on:click={() => openSite(e.code)}>
      <header class="es-header">
        <div class="es-logo">
          {#if e.has_logo}
            <img src={logoUrl(e)} alt={e.code} />
          {:else}
            <span class="es-logo-fallback" style="background: {e.color}">{e.code}</span>
          {/if}
        </div>
        <div class="es-meta">
          <span class="es-code">{e.code}</span>
          <span class="es-name" title={e.name}>{e.name}</span>
        </div>
      </header>
      <div class="es-stats">
        <div class="es-stat">
          <span class="es-stat-val">{tasks}</span>
          <span class="es-stat-label">tâche{tasks > 1 ? 's' : ''}</span>
        </div>
        <div class="es-stat" class:es-stat--warn={overdue > 0}>
          <span class="es-stat-val">{overdue}</span>
          <span class="es-stat-label">en retard</span>
        </div>
        <div class="es-stat">
          <span class="es-stat-val">{projects}</span>
          <span class="es-stat-label">projet{projects > 1 ? 's' : ''}</span>
        </div>
        <div class="es-stat">
          <span class="es-stat-val">{events}</span>
          <span class="es-stat-label">event{events > 1 ? 's' : ''} 7j</span>
        </div>
      </div>
    </article>
  {/each}

  {#if $establishments.length === 0 && loaded}
    <p class="es-empty">Aucun établissement configuré. Va dans Paramètres → Établissements.</p>
  {/if}
</div>

<style>
  .es-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 1rem;
    padding: 1rem 1.25rem;
  }

  .es-empty {
    grid-column: 1 / -1;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.875rem;
    padding: 2rem;
    margin: 0;
  }

  .es-card {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.75rem;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.875rem;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
    border-top: 3px solid var(--accent, var(--primary));
  }
  .es-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  }

  .es-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  .es-logo {
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    border-radius: 0.5rem;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.04);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .es-logo img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }
  .es-logo-fallback {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-weight: 700;
    font-size: 0.875rem;
  }
  .es-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    flex: 1;
  }
  .es-code {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: var(--accent, var(--primary));
  }
  .es-name {
    font-size: 0.8125rem;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .es-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.5rem;
  }
  .es-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.5rem 0.25rem;
    background: var(--bg-base);
    border-radius: 0.5rem;
    text-align: center;
  }
  .es-stat-val {
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--text-heading);
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
  }
  .es-stat-label {
    font-size: 0.625rem;
    color: var(--text-muted);
    margin-top: 2px;
    text-align: center;
  }
  .es-stat--warn .es-stat-val {
    color: #EF4444;
  }
</style>
