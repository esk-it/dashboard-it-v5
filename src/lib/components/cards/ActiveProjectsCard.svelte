<script>
  import { onMount } from 'svelte';
  import { api } from '../../api/client.js';
  import { currentPage } from '../../stores/navigation.js';

  let tasks = [];
  let loading = true;

  const STATUS_COLORS = {
    open: { bg: 'rgba(69, 43, 144, 0.15)', text: '#8869e1', label: 'En cours' },
    done: { bg: 'rgba(58, 155, 148, 0.15)', text: '#3A9B94', label: 'Termine' },
    overdue: { bg: 'rgba(255, 94, 94, 0.15)', text: '#FF5E5E', label: 'En retard' },
    pending: { bg: 'rgba(255, 159, 0, 0.15)', text: '#FF9F00', label: 'En attente' },
  };

  const PROGRESS_COLORS = ['#452B90', '#3A9B94', '#F8B940', '#FF5E5E', '#58bad7', '#EC4899'];

  export async function refresh() { await load(); }

  onMount(load);

  async function load() {
    loading = true;
    try {
      const data = await api.get('/api/dashboard/top-tasks');
      const raw = data.tasks || data || [];
      tasks = raw.slice(0, 8);
    } catch {
      tasks = [];
    }
    loading = false;
  }

  function getStatus(task) {
    if (task.status === 'done' || task.status === 'completed') return STATUS_COLORS.done;
    if (task.is_overdue || (task.due_date && new Date(task.due_date) < new Date() && task.status !== 'done'))
      return STATUS_COLORS.overdue;
    if (task.status === 'pending') return STATUS_COLORS.pending;
    return STATUS_COLORS.open;
  }

  function getProgress(task) {
    if (task.progress != null) return task.progress;
    if (task.status === 'done' || task.status === 'completed') return 100;
    if (task.checklist_total && task.checklist_done != null)
      return Math.round((task.checklist_done / task.checklist_total) * 100);
    return Math.floor(Math.random() * 60 + 20); // fallback visual
  }

  function formatDate(dateStr) {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  }

  function priorityLabel(p) {
    if (p === 1 || p === 'P1') return 'Haute';
    if (p === 3 || p === 'P3') return 'Basse';
    return 'Normale';
  }

  function priorityColor(p) {
    if (p === 1 || p === 'P1') return { bg: 'rgba(255,94,94,0.15)', text: '#FF5E5E' };
    if (p === 3 || p === 'P3') return { bg: 'rgba(58,155,148,0.15)', text: '#3A9B94' };
    return { bg: 'rgba(69,43,144,0.15)', text: '#8869e1' };
  }
</script>

<div class="active-projects">
  {#if loading}
    <div class="ap-empty">Chargement...</div>
  {:else if tasks.length === 0}
    <div class="ap-empty">Aucune tache active</div>
  {:else}
    <div class="ap-table-wrap">
      <table class="ap-table">
        <thead>
          <tr>
            <th>Tache</th>
            <th>Priorite</th>
            <th>Echeance</th>
            <th>Statut</th>
            <th>Progression</th>
          </tr>
        </thead>
        <tbody>
          {#each tasks as task, i}
            {@const status = getStatus(task)}
            {@const progress = getProgress(task)}
            {@const prio = priorityColor(task.priority)}
            <tr>
              <td>
                <span class="ap-task-title">{task.title || task.name || ''}</span>
                {#if task.category}
                  <span class="ap-task-cat">{task.category}</span>
                {/if}
              </td>
              <td>
                <span class="ap-badge" style="background:{prio.bg};color:{prio.text}">
                  {priorityLabel(task.priority)}
                </span>
              </td>
              <td class="ap-date">{formatDate(task.due_date)}</td>
              <td>
                <span class="ap-badge" style="background:{status.bg};color:{status.text}">
                  {status.label}
                </span>
              </td>
              <td>
                <div class="ap-progress">
                  <div class="ap-progress__bar">
                    <div
                      class="ap-progress__fill"
                      style="width:{progress}%;background:{PROGRESS_COLORS[i % PROGRESS_COLORS.length]}"
                    ></div>
                  </div>
                  <span class="ap-progress__text">{progress}%</span>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .active-projects {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .ap-empty {
    padding: 2rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8125rem;
  }

  .ap-table-wrap {
    overflow-x: auto;
  }

  .ap-table {
    width: 100%;
    border-collapse: collapse;
  }

  .ap-table thead th {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    padding: 0.75rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border-subtle);
    white-space: nowrap;
  }

  .ap-table tbody tr {
    transition: background 0.15s;
  }

  .ap-table tbody tr:hover {
    background: var(--bg-hover);
  }

  .ap-table tbody td {
    padding: 0.625rem 1rem;
    font-size: 0.8125rem;
    color: var(--text-primary);
    border-bottom: 1px solid var(--border-subtle);
    vertical-align: middle;
  }

  .ap-task-title {
    display: block;
    font-weight: 500;
    color: var(--text-heading);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 220px;
  }

  .ap-task-cat {
    display: inline-block;
    font-size: 0.6875rem;
    color: var(--text-muted);
    margin-top: 0.125rem;
  }

  .ap-badge {
    display: inline-block;
    padding: 0.1875rem 0.625rem;
    border-radius: 0.375rem;
    font-size: 0.6875rem;
    font-weight: 600;
    white-space: nowrap;
    border: 0;
  }

  .ap-date {
    white-space: nowrap;
    color: var(--text-secondary);
  }

  .ap-progress {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 120px;
  }

  .ap-progress__bar {
    flex: 1;
    height: 0.3125rem;
    background: rgba(255,255,255,0.08);
    border-radius: 1rem;
    overflow: hidden;
  }

  .ap-progress__fill {
    height: 100%;
    border-radius: 1rem;
    transition: width 0.6s ease-out;
  }

  .ap-progress__text {
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--text-secondary);
    min-width: 2rem;
    text-align: right;
  }
</style>
