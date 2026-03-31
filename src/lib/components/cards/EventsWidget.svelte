<script>
  import { onMount } from 'svelte';
  import { api } from '../../api/client.js';
  import { Calendar } from 'lucide-svelte';
  import GlassCard from '../GlassCard.svelte';

  let events = [];
  let loading = true;

  export function refresh() {
    fetchEvents();
  }

  onMount(() => {
    fetchEvents();
  });

  async function fetchEvents() {
    loading = true;
    try {
      const data = await api.get('/api/planning?upcoming=5');
      events = data.events || data || [];
    } catch (e) {
      events = [];
    }
    loading = false;
  }

  function formatDay(dateStr) {
    if (!dateStr) return { day: '--', weekday: '---' };
    const d = new Date(dateStr);
    const day = d.getDate();
    const weekday = d.toLocaleDateString('fr-FR', { weekday: 'short' }).replace('.', '');
    return { day, weekday };
  }

  function formatTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  const badgeColors = ['#452B90', '#F8B940', '#3A9B94', '#FF5E5E', '#58bad7'];
</script>

<GlassCard padding="0">
  <div class="card-inner">
    <div class="card-header">
      <h3>
        <Calendar size={15} style="display:inline;vertical-align:-2px;margin-right:6px;" />
        Prochains &eacute;v&eacute;nements
      </h3>
    </div>

    <div class="events-list">
      {#if loading}
        <div class="empty">Chargement...</div>
      {:else if events.length === 0}
        <div class="empty">Aucun &eacute;v&eacute;nement &agrave; venir</div>
      {:else}
        {#each events as event, i}
          {@const dateInfo = formatDay(event.start || event.date)}
          <div class="event-item">
            <div class="date-badge" style="background: {badgeColors[i % badgeColors.length]};">
              <span class="date-day">{dateInfo.day}</span>
              <span class="date-weekday">{dateInfo.weekday}</span>
            </div>
            <div class="event-info">
              <span class="event-title">{event.title || event.name || ''}</span>
              <span class="event-time">{formatTime(event.start || event.date)}</span>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>
</GlassCard>

<style>
  .card-inner {
    display: flex;
    flex-direction: column;
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

  .events-list {
    padding: 8px 12px;
  }

  .event-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 8px;
    border-bottom: 1px solid var(--border-subtle);
    transition: background 0.15s;
  }

  .event-item:last-child {
    border-bottom: none;
  }

  .event-item:hover {
    background: var(--bg-hover);
    border-radius: 8px;
  }

  .date-badge {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: 10px;
    flex-shrink: 0;
    color: #fff;
  }

  .date-day {
    font-size: 16px;
    font-weight: 700;
    line-height: 1.1;
  }

  .date-weekday {
    font-size: 10px;
    font-weight: 500;
    text-transform: uppercase;
    opacity: 0.85;
  }

  .event-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .event-title {
    font-size: 13.5px;
    color: var(--text-primary);
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .event-time {
    font-size: 11.5px;
    color: var(--text-muted);
  }

  .empty {
    padding: 24px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }
</style>
