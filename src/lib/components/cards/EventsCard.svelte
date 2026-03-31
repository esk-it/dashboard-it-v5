<script>
  import { onMount } from 'svelte';
  import { api } from '../../api/client.js';
  import { currentPage } from '../../stores/navigation.js';

  let events = [];
  let loading = true;

  const EVENT_COLORS = {
    meeting: '#4B8BFF',
    intervention: '#F59E0B',
    maintenance: '#8B5CF6',
    leave: '#22C55E',
    milestone: '#EC4899',
    other: '#64748B',
  };

  const EVENT_EMOJIS = {
    meeting: '\u{1F91D}',
    intervention: '\u{1F527}',
    maintenance: '\u2699\uFE0F',
    leave: '\u{1F3D6}\uFE0F',
    milestone: '\u{1F3C1}',
    other: '\u{1F4CC}',
  };

  export async function refresh() { await load(); }

  onMount(load);

  async function load() {
    loading = true;
    try {
      const data = await api.get('/api/planning/events');
      const raw = data.events || data || [];
      // Sort by date ascending, take next 6
      events = raw
        .filter(e => e.start_date || e.date)
        .sort((a, b) => new Date(a.start_date || a.date) - new Date(b.start_date || b.date))
        .slice(0, 6);
    } catch {
      events = [];
    }
    loading = false;
  }

  function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  }

  function formatTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const h = d.getHours();
    const m = d.getMinutes();
    if (h === 0 && m === 0) return '';
    return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  function getColor(type) {
    return EVENT_COLORS[type] || EVENT_COLORS.other;
  }

  function getEmoji(type) {
    return EVENT_EMOJIS[type] || EVENT_EMOJIS.other;
  }

  // Mini calendar
  $: today = new Date();
  $: currentMonth = today.getMonth();
  $: currentYear = today.getFullYear();
  $: monthName = today.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
  $: calDays = buildCalDays(currentYear, currentMonth);

  function buildCalDays(year, month) {
    const first = new Date(year, month, 1);
    const last = new Date(year, month + 1, 0);
    let startDay = first.getDay();
    if (startDay === 0) startDay = 7;
    startDay--;

    const days = [];
    // Previous month filler
    for (let i = 0; i < startDay; i++) days.push({ num: '', current: false });
    // Current month
    for (let d = 1; d <= last.getDate(); d++) {
      days.push({
        num: d,
        current: true,
        isToday: d === today.getDate() && month === today.getMonth() && year === today.getFullYear(),
      });
    }
    return days;
  }
</script>

<div class="events-widget">
  <!-- Mini Calendar -->
  <div class="mini-cal">
    <div class="mini-cal__header">
      <span class="mini-cal__month">{monthName}</span>
    </div>
    <div class="mini-cal__grid">
      {#each ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di'] as day}
        <span class="mini-cal__day-name">{day}</span>
      {/each}
      {#each calDays as day}
        <span
          class="mini-cal__day"
          class:mini-cal__day--today={day.isToday}
          class:mini-cal__day--empty={!day.current}
        >{day.num}</span>
      {/each}
    </div>
  </div>

  <!-- Events list -->
  <div class="events-list">
    <h4 class="events-list__title">Prochains evenements</h4>
    {#if loading}
      <div class="events-empty">Chargement...</div>
    {:else if events.length === 0}
      <div class="events-empty">Aucun evenement a venir</div>
    {:else}
      <div class="events-scroll">
        {#each events as evt}
          <div class="event-item">
            <div class="event-box" style="background: {getColor(evt.event_type || evt.type)}"></div>
            <div class="event-data">
              <span class="event-title">{evt.title || evt.name || ''}</span>
              <span class="event-meta">
                {getEmoji(evt.event_type || evt.type)}
                {formatDate(evt.start_date || evt.date)}
                {#if formatTime(evt.start_date || evt.date)}
                  <span class="event-time">{formatTime(evt.start_date || evt.date)}</span>
                {/if}
              </span>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="events-footer" on:click={() => currentPage.set('/planning')}>
    Voir le planning &rarr;
  </div>
</div>

<style>
  .events-widget {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  /* ── Mini Calendar ── */
  .mini-cal {
    padding: 1rem 1.25rem 0.75rem;
  }

  .mini-cal__header {
    margin-bottom: 0.5rem;
  }

  .mini-cal__month {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--text-heading);
    text-transform: capitalize;
  }

  .mini-cal__grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 1px;
    text-align: center;
  }

  .mini-cal__day-name {
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    padding: 0.25rem 0;
  }

  .mini-cal__day {
    font-size: 0.6875rem;
    color: var(--text-secondary);
    padding: 0.25rem 0;
    border-radius: 50%;
    line-height: 1.6;
  }

  .mini-cal__day--today {
    background: var(--primary);
    color: #fff;
    font-weight: 700;
  }

  .mini-cal__day--empty {
    visibility: hidden;
  }

  /* ── Events list ── */
  .events-list {
    flex: 1;
    padding: 0 1.25rem;
    min-height: 0;
  }

  .events-list__title {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-heading);
    margin: 0 0 0.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-subtle);
  }

  .events-scroll {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-height: 200px;
    overflow-y: auto;
  }

  .events-empty {
    padding: 1.5rem 0;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8125rem;
  }

  .event-item {
    display: flex;
    align-items: flex-start;
    gap: 0.625rem;
    padding: 0.375rem 0;
  }

  .event-box {
    width: 0.25rem;
    min-height: 2rem;
    border-radius: 0.25rem;
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  .event-data {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    min-width: 0;
  }

  .event-title {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-heading);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .event-meta {
    font-size: 0.6875rem;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .event-time {
    color: var(--text-secondary);
    font-weight: 500;
  }

  /* ── Footer ── */
  .events-footer {
    padding: 0.75rem 1.25rem;
    border-top: 1px solid var(--border-subtle);
    text-align: center;
    font-size: 0.75rem;
    color: var(--primary);
    cursor: pointer;
    transition: background 0.15s;
    margin-top: auto;
  }

  .events-footer:hover {
    background: var(--bg-hover);
  }
</style>
