<script>
  // Horizontal-scroll showcase of in-progress projects, inspired by YashAdmin's
  // "Running Projects" card. Adapted for a solo IT manager: no team avatars —
  // instead we surface task count, doc count and supplier count as concrete
  // signal for "where am I on this project?".
  //
  // Click on a tile sets `projects.focusId` in sessionStorage and navigates to
  // /projects so the page can scroll-and-flash the corresponding row when it
  // mounts. (Same pattern used for the Documents → Suppliers cross-nav.)

  import { onMount } from 'svelte';
  import { api } from '../../api/client.js';
  import { currentPage } from '../../stores/navigation.js';
  import EstablishmentBadge from '../EstablishmentBadge.svelte';

  let projects = [];
  let loaded = false;

  export function refresh() { fetchData(); }

  onMount(() => fetchData());

  async function fetchData() {
    try {
      const all = await api.get('/api/projects');
      projects = (all || []).filter(p => p.status === 'in_progress');
    } catch {
      projects = [];
    }
    loaded = true;
  }

  function openProject(p) {
    try { sessionStorage.setItem('projects.focusId', String(p.id)); } catch {}
    currentPage.set('/projects');
  }

  function fmtDate(iso) {
    if (!iso) return '';
    // Local-midnight normalisation (avoids the YYYY-MM-DD → UTC shift).
    const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return '';
    const d = new Date(+m[1], +m[2] - 1, +m[3]);
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
  }

  function dueState(p) {
    if (!p.end_date) return null;
    const m = String(p.end_date).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return null;
    const due = new Date(+m[1], +m[2] - 1, +m[3]).getTime();
    const today = new Date(); today.setHours(0,0,0,0);
    const days = Math.round((due - today.getTime()) / 86400000);
    if (days < 0) return { kind: 'overdue', label: `J${days}` };
    if (days === 0) return { kind: 'soon', label: "Aujourd'hui" };
    if (days <= 7) return { kind: 'soon', label: `J-${days}` };
    return { kind: 'ok', label: fmtDate(p.end_date) };
  }

  function projectInitial(title) {
    const t = (title || '?').trim();
    return t.split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase().slice(0, 2);
  }
</script>

<div class="rp-wrap">
  {#if !loaded}
    <div class="rp-empty">Chargement…</div>
  {:else if projects.length === 0}
    <div class="rp-empty">Aucun projet en cours pour le moment.</div>
  {:else}
    <div class="rp-scroll">
      {#each projects as p}
        {@const ds = dueState(p)}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <article class="rp-card" on:click={() => openProject(p)}>
          <div class="rp-banner" style="background:linear-gradient(135deg, {p.color} 0%, {p.color}cc 100%)">
            <span class="rp-initial">{projectInitial(p.title)}</span>
            {#if p.site}
              <span class="rp-site-pill">
                <EstablishmentBadge code={p.site} size="xs" showLabel={true} />
              </span>
            {/if}
            {#if ds}
              <span class="rp-due-pill rp-due-pill--{ds.kind}">{ds.label}</span>
            {/if}
          </div>
          <div class="rp-body">
            <h4 class="rp-title" title={p.title}>{p.title}</h4>
            {#if p.description}
              <p class="rp-desc">{p.description}</p>
            {/if}
            <div class="rp-progress">
              <div class="rp-bar"><div class="rp-bar-fill" style="width:{p.progress}%;background:{p.color}"></div></div>
              <span class="rp-pct">{p.progress}%</span>
            </div>
            <div class="rp-stats">
              <div class="rp-stat">
                <span class="rp-stat-val">{p.done_tasks}<span class="rp-stat-sep">/</span>{p.total_tasks}</span>
                <span class="rp-stat-label">tâches</span>
              </div>
              <div class="rp-stat">
                <span class="rp-stat-val">{p.document_count}</span>
                <span class="rp-stat-label">docs</span>
              </div>
              <div class="rp-stat">
                <span class="rp-stat-val">{p.supplier_count}</span>
                <span class="rp-stat-label">presta.</span>
              </div>
            </div>
          </div>
        </article>
      {/each}
    </div>
  {/if}
</div>

<style>
  .rp-wrap { width: 100%; }

  .rp-empty {
    padding: 2.5rem 1.25rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8125rem;
  }

  /* Horizontal scroll container — mandatory snapping so each card aligns nicely */
  .rp-scroll {
    display: flex;
    gap: 1rem;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 0.5rem 1.25rem 1.25rem;
    scroll-snap-type: x mandatory;
    scrollbar-width: thin;
  }
  .rp-scroll::-webkit-scrollbar { height: 8px; }
  .rp-scroll::-webkit-scrollbar-track { background: transparent; }
  .rp-scroll::-webkit-scrollbar-thumb {
    background: var(--border-subtle);
    border-radius: 4px;
  }
  .rp-scroll::-webkit-scrollbar-thumb:hover { background: var(--border-hover, #555); }

  /* Project tile */
  .rp-card {
    flex: 0 0 280px;
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.75rem;
    overflow: hidden;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
    scroll-snap-align: start;
    display: flex;
    flex-direction: column;
  }
  .rp-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 30px rgba(0,0,0,0.18);
  }

  .rp-banner {
    height: 70px;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .rp-initial {
    font-size: 1.625rem;
    font-weight: 700;
    color: #fff;
    letter-spacing: 0.05em;
    text-shadow: 0 1px 3px rgba(0,0,0,0.2);
  }
  .rp-due-pill {
    position: absolute;
    top: 8px;
    right: 8px;
    padding: 2px 8px;
    font-size: 0.625rem;
    font-weight: 700;
    border-radius: 1rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  /* Establishment badge on the banner — top-left, semi-transparent backing so
     it reads on any project color. */
  .rp-site-pill {
    position: absolute;
    top: 8px;
    left: 8px;
    padding: 2px 6px;
    background: rgba(255, 255, 255, 0.92);
    border-radius: 0.625rem;
    display: inline-flex;
    align-items: center;
    line-height: 1;
  }
  .rp-due-pill--ok {
    background: rgba(255,255,255,0.25);
    color: #fff;
  }
  .rp-due-pill--soon {
    background: rgba(248, 185, 64, 0.95);
    color: #1a1a1a;
  }
  .rp-due-pill--overdue {
    background: rgba(239, 68, 68, 0.95);
    color: #fff;
  }

  .rp-body {
    padding: 0.875rem 1rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    flex: 1;
  }
  .rp-title {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-heading);
    margin: 0;
    line-height: 1.3;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .rp-desc {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin: 0;
    line-height: 1.35;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 2.05em;
  }
  .rp-progress {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.125rem;
  }
  .rp-bar {
    flex: 1;
    height: 6px;
    background: var(--bg-base);
    border-radius: 3px;
    overflow: hidden;
  }
  .rp-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease-out;
    min-width: 2px;
  }
  .rp-pct {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--text-heading);
    min-width: 36px;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .rp-stats {
    display: flex;
    gap: 0.875rem;
    border-top: 1px solid var(--border-subtle);
    padding-top: 0.625rem;
    margin-top: 0.25rem;
  }
  .rp-stat {
    display: flex;
    flex-direction: column;
    gap: 1px;
    flex: 1;
  }
  .rp-stat-val {
    font-size: 0.9375rem;
    font-weight: 700;
    color: var(--text-heading);
    line-height: 1.1;
  }
  .rp-stat-sep {
    color: var(--text-muted);
    font-weight: 400;
    margin: 0 1px;
  }
  .rp-stat-label {
    font-size: 0.6875rem;
    color: var(--text-muted);
  }
</style>
