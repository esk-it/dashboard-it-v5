<script>
  import { onMount } from 'svelte';
  import { api } from '../../api/client.js';
  import { currentPage } from '../../stores/navigation.js';
  import { Target, ChevronRight } from 'lucide-svelte';
  import GlassCard from '../GlassCard.svelte';

  let tasks = [];
  let loading = true;

  export function refresh() {
    loadTasks();
  }

  onMount(() => {
    loadTasks();
  });

  async function loadTasks() {
    loading = true;
    try {
      const data = await api.get('/api/dashboard/top-tasks');
      tasks = data.tasks || data || [];
    } catch (e) {
      tasks = [];
    }
    loading = false;
  }

  function goToTasks() {
    currentPage.set('/tasks');
  }

  function priorityClass(priority) {
    if (priority === 1 || priority === 'P1') return 'p1';
    if (priority === 2 || priority === 'P2') return 'p2';
    return 'p3';
  }

  function priorityLabel(priority) {
    if (priority === 1 || priority === 'P1') return 'P1';
    if (priority === 2 || priority === 'P2') return 'P2';
    return 'P3';
  }

  function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  }
</script>

<GlassCard padding="0">
  <div class="card-inner">
    <div class="card-header">
      <h3>
        <Target size={15} style="display:inline;vertical-align:-2px;margin-right:6px;color:var(--primary)" />
        T&acirc;ches prioritaires
      </h3>
    </div>

    <div class="task-list">
      {#if loading}
        <div class="empty">Chargement...</div>
      {:else if tasks.length === 0}
        <div class="empty">Aucune t&acirc;che prioritaire</div>
      {:else}
        {#each tasks as task}
          <div class="task-item">
            <span class="priority-badge {priorityClass(task.priority)}">
              {priorityLabel(task.priority)}
            </span>
            <div class="task-info">
              <span class="task-title">{task.title || task.name || ''}</span>
              {#if task.due_date}
                <span class="task-due">{formatDate(task.due_date)}</span>
              {/if}
            </div>
            {#if task.category}
              <span class="task-category">{task.category}</span>
            {/if}
          </div>
        {/each}
      {/if}
    </div>

    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="card-footer" on:click={goToTasks}>
      Voir toutes les t&acirc;ches
      <ChevronRight size={14} style="display:inline;vertical-align:-2px;margin-left:4px;" />
    </div>
  </div>
</GlassCard>

<style>
  .card-inner {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .card-header {
    padding: 16px 20px 12px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .card-header h3 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
    display: flex;
    align-items: center;
  }

  .task-list {
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-height: 280px;
    overflow-y: auto;
  }

  .empty {
    padding: 24px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }

  .task-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 8px;
    border-radius: 8px;
    transition: background 0.15s;
  }

  .task-item:hover {
    background: var(--bg-hover);
  }

  .priority-badge {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 6px;
    flex-shrink: 0;
  }

  .priority-badge.p1 {
    background: rgba(255, 94, 94, 0.15);
    color: #FF5E5E;
  }

  .priority-badge.p2 {
    background: rgba(248, 185, 64, 0.15);
    color: #F8B940;
  }

  .priority-badge.p3 {
    background: rgba(var(--primary-rgb), 0.15);
    color: var(--primary);
  }

  .task-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .task-title {
    font-size: 13.5px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .task-due {
    font-size: 11px;
    color: var(--text-muted);
  }

  .task-category {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 6px;
    background: rgba(var(--primary-rgb), 0.08);
    color: var(--text-secondary);
    white-space: nowrap;
  }

  .card-footer {
    padding: 12px 20px;
    border-top: 1px solid var(--border-subtle);
    text-align: center;
    font-size: 12.5px;
    color: var(--primary);
    cursor: pointer;
    transition: background 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .card-footer:hover {
    background: var(--bg-hover);
  }
</style>
