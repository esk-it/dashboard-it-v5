<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../api/client.js';
  import { currentPage } from '../stores/navigation.js';
  import { Calendar } from '@fullcalendar/core';
  import dayGridPlugin from '@fullcalendar/daygrid';
  import timeGridPlugin from '@fullcalendar/timegrid';
  import listPlugin from '@fullcalendar/list';
  import interactionPlugin from '@fullcalendar/interaction';

  // ---------------------------------------------------------------------------
  // Constants
  // ---------------------------------------------------------------------------
  const EVENT_TYPES = {
    meeting:      { emoji: '\u{1F91D}', label: 'Reunion',      color: '#4B8BFF' },
    intervention: { emoji: '\u{1F527}', label: 'Intervention',  color: '#F59E0B' },
    maintenance:  { emoji: '\u2699\uFE0F',  label: 'Maintenance',   color: '#8B5CF6' },
    leave:        { emoji: '\u{1F3D6}\uFE0F',  label: 'Conge',        color: '#22C55E' },
    milestone:    { emoji: '\u{1F3C1}', label: 'Jalon',         color: '#EC4899' },
    other:        { emoji: '\u{1F4CC}', label: 'Autre',         color: '#64748B' },
  };

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  let calendarEl;
  let calendar;
  let events = [];
  let calendarTasks = [];

  // Dialog
  let showDialog = false;
  let editingEvent = null;
  let form = defaultForm();
  let openTasks = [];

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  function defaultForm() {
    return {
      title: '',
      event_type: 'other',
      date_start: toDateStr(new Date()),
      date_end: toDateStr(new Date()),
      all_day: true,
      time_start: '09:00',
      time_end: '10:00',
      person: '',
      notes: '',
      task_id: null,
    };
  }

  function toDateStr(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${dd}`;
  }

  function getEventColor(type) {
    return EVENT_TYPES[type]?.color || '#64748B';
  }

  function getEventEmoji(type) {
    return EVENT_TYPES[type]?.emoji || '\u{1F4CC}';
  }

  // ---------------------------------------------------------------------------
  // API
  // ---------------------------------------------------------------------------
  async function fetchEvents() {
    if (!calendar) return;
    const view = calendar.view;
    const start = toDateStr(view.activeStart);
    const end = toDateStr(view.activeEnd);

    try {
      const [evts, tasks] = await Promise.all([
        api.get(`/api/planning/events?start=${start}&end=${end}`),
        api.get(`/api/planning/tasks-for-calendar?start=${start}&end=${end}`),
      ]);
      events = evts;
      calendarTasks = tasks;
      updateCalendarEvents();
    } catch (e) {
      console.error('Failed to fetch planning data', e);
    }
  }

  function updateCalendarEvents() {
    if (!calendar) return;

    // Remove existing event sources
    calendar.removeAllEvents();

    // Add planning events
    const fcEvents = events.map(evt => {
      const color = getEventColor(evt.event_type);
      const start = evt.all_day
        ? evt.date_start
        : `${evt.date_start}T${evt.time_start || '00:00'}`;
      const end = evt.all_day
        ? addOneDay(evt.date_end)
        : (evt.time_end ? `${evt.date_end}T${evt.time_end}` : null);

      return {
        id: `event-${evt.id}`,
        title: `${getEventEmoji(evt.event_type)} ${evt.title}`,
        start,
        end,
        allDay: evt.all_day,
        backgroundColor: color,
        borderColor: color,
        textColor: '#fff',
        extendedProps: { ...evt, _type: 'event' },
      };
    });

    // Add tasks
    const fcTasks = calendarTasks.map(t => ({
      id: `task-${t.id}`,
      title: `\u2705 ${t.title}`,
      start: t.due_date,
      allDay: true,
      backgroundColor: '#4B8BFF',
      borderColor: '#4B8BFF',
      textColor: '#fff',
      extendedProps: { ...t, _type: 'task' },
    }));

    calendar.addEventSource([...fcEvents, ...fcTasks]);
  }

  function addOneDay(dateStr) {
    const d = new Date(dateStr);
    d.setDate(d.getDate() + 1);
    return toDateStr(d);
  }

  async function fetchOpenTasks() {
    try {
      openTasks = await api.get('/api/tasks?status=open');
    } catch {
      openTasks = [];
    }
  }

  async function saveEvent() {
    const payload = { ...form };
    if (payload.all_day) {
      payload.time_start = null;
      payload.time_end = null;
    }
    if (!payload.task_id) payload.task_id = null;

    try {
      if (editingEvent) {
        await api.put(`/api/planning/events/${editingEvent.id}`, payload);
      } else {
        await api.post('/api/planning/events', payload);
      }
      showDialog = false;
      await fetchEvents();
    } catch (e) {
      console.error('Failed to save event', e);
    }
  }

  async function deleteEvent() {
    if (!editingEvent) return;
    try {
      await api.delete(`/api/planning/events/${editingEvent.id}`);
      showDialog = false;
      await fetchEvents();
    } catch (e) {
      console.error('Failed to delete event', e);
    }
  }

  // ---------------------------------------------------------------------------
  // Dialog helpers
  // ---------------------------------------------------------------------------
  function openNewEvent(dateStr, timeStr = null) {
    editingEvent = null;
    form = defaultForm();
    form.date_start = dateStr;
    form.date_end = dateStr;
    if (timeStr) {
      form.all_day = false;
      form.time_start = timeStr;
      const [h, m] = timeStr.split(':').map(Number);
      form.time_end = `${String(h + 1).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    }
    fetchOpenTasks();
    showDialog = true;
  }

  function openEditEvent(evt) {
    if (evt._type === 'task') {
      currentPage.set('/tasks');
      return;
    }
    editingEvent = evt;
    form = {
      title: evt.title,
      event_type: evt.event_type || 'other',
      date_start: evt.date_start,
      date_end: evt.date_end,
      all_day: evt.all_day,
      time_start: evt.time_start || '09:00',
      time_end: evt.time_end || '10:00',
      person: evt.person || '',
      notes: evt.notes || '',
      task_id: evt.task_id || null,
    };
    fetchOpenTasks();
    showDialog = true;
  }

  // ---------------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------------
  onMount(() => {
    calendar = new Calendar(calendarEl, {
      plugins: [dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin],
      initialView: 'dayGridMonth',
      locale: 'fr',
      firstDay: 1, // Monday
      headerToolbar: {
        left: 'prev,next today',
        center: 'title',
        right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek',
      },
      buttonText: {
        today: "Aujourd'hui",
        month: 'Mois',
        week: 'Semaine',
        day: 'Jour',
        list: 'Liste',
      },
      height: 'auto',
      contentHeight: 'auto',
      expandRows: true,
      dayMaxEvents: 3,
      weekNumbers: true,
      navLinks: true,
      editable: false,
      selectable: true,
      selectMirror: true,
      nowIndicator: true,
      slotMinTime: '07:00:00',
      slotMaxTime: '20:00:00',
      slotDuration: '00:30:00',
      allDayText: 'Journee',
      noEventsText: 'Aucun evenement',

      // Callbacks
      datesSet: () => {
        fetchEvents();
      },

      dateClick: (info) => {
        if (info.allDay || info.view.type === 'dayGridMonth') {
          openNewEvent(toDateStr(info.date));
        } else {
          const h = String(info.date.getHours()).padStart(2, '0');
          const m = String(info.date.getMinutes()).padStart(2, '0');
          openNewEvent(toDateStr(info.date), `${h}:${m}`);
        }
      },

      select: (info) => {
        openNewEvent(toDateStr(info.start));
      },

      eventClick: (info) => {
        const props = info.event.extendedProps;
        openEditEvent(props);
      },
    });

    calendar.render();
  });

  onDestroy(() => {
    if (calendar) calendar.destroy();
  });
</script>

<div class="planning-page">
  <div class="planning-layout">
    <!-- ═══ Left sidebar — event types (YashAdmin style) ═══ -->
    <div class="planning-sidebar">
      <div class="ya-page-card">
        <div class="ya-page-card__body">
          <h4 class="sidebar-title">Calendrier</h4>
          <p class="sidebar-desc">Cliquez sur le calendrier pour creer un evenement</p>

          <div class="external-events">
            {#each Object.entries(EVENT_TYPES) as [key, t]}
              <div class="external-event" style="--evt-color:{t.color}">
                <span class="external-event__dot" style="background:{t.color}"></span>
                <span>{t.label}</span>
              </div>
            {/each}
            <div class="external-event" style="--evt-color:#4B8BFF">
              <span class="external-event__dot" style="background:#4B8BFF"></span>
              <span>Tache</span>
            </div>
          </div>

          <button class="ya-btn ya-btn--primary" style="width:100%;margin-top:1.5rem" on:click={() => openNewEvent(toDateStr(new Date()))}>
            + Creer un evenement
          </button>
        </div>
      </div>
    </div>

    <!-- ═══ Right — FullCalendar ═══ -->
    <div class="planning-main">
      <div class="ya-page-card">
        <div class="ya-page-card__body app-fullcalendar">
          <div bind:this={calendarEl}></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Event dialog -->
{#if showDialog}
  <div class="ya-dialog-overlay" on:click|self={() => showDialog = false}>
    <div class="ya-dialog">
      <div class="ya-dialog__header">
        <h3 class="ya-dialog__title">{editingEvent ? 'Modifier l\'evenement' : 'Nouvel evenement'}</h3>
        <button class="ya-dialog__close" on:click={() => showDialog = false}>&times;</button>
      </div>

      <div class="ya-dialog__body">
        <label class="field">
          <span>Titre *</span>
          <input type="text" bind:value={form.title} placeholder="Titre de l'evenement" />
        </label>

        <div class="field">
          <span>Type</span>
          <div class="type-selector">
            {#each Object.entries(EVENT_TYPES) as [key, t]}
              <button
                class="type-option"
                class:selected={form.event_type === key}
                style="--type-color:{t.color}"
                on:click={() => form.event_type = key}
                title={t.label}
              >
                <span class="type-emoji">{t.emoji}</span>
                <span class="type-label">{t.label}</span>
              </button>
            {/each}
          </div>
        </div>

        <label class="field">
          <span>Personne</span>
          <input type="text" bind:value={form.person} placeholder="Optionnel" />
        </label>

        <div class="field-row">
          <label class="field">
            <span>Date debut</span>
            <input type="date" bind:value={form.date_start} />
          </label>
          <label class="field">
            <span>Date fin</span>
            <input type="date" bind:value={form.date_end} min={form.date_start} />
          </label>
        </div>

        <label class="field checkbox-field">
          <input type="checkbox" bind:checked={form.all_day} />
          <span>Journee entiere</span>
        </label>

        {#if !form.all_day}
          <div class="field-row">
            <label class="field">
              <span>Heure debut</span>
              <input type="time" bind:value={form.time_start} />
            </label>
            <label class="field">
              <span>Heure fin</span>
              <input type="time" bind:value={form.time_end} />
            </label>
          </div>
        {/if}

        <label class="field">
          <span>Notes</span>
          <textarea bind:value={form.notes} rows="3" placeholder="Notes optionnelles"></textarea>
        </label>

        <label class="field">
          <span>Lier a une tache</span>
          <select bind:value={form.task_id}>
            <option value={null}>-- Aucune --</option>
            {#each openTasks as t}
              <option value={t.id}>{t.title}</option>
            {/each}
          </select>
        </label>
      </div>

      <div class="ya-dialog__footer">
        {#if editingEvent}
          <button class="ya-btn" style="background:var(--danger);color:#fff;margin-right:auto" on:click={deleteEvent}>
            Supprimer
          </button>
        {/if}
        <button class="ya-btn ya-btn--ghost" on:click={() => showDialog = false}>Annuler</button>
        <button class="ya-btn ya-btn--primary" on:click={saveEvent} disabled={!form.title.trim()}>
          {editingEvent ? 'Enregistrer' : 'Creer'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .planning-page {
    animation: fadeIn 0.35s ease-out;
  }

  /* ── 2-column layout (YashAdmin calendar style) ── */
  .planning-layout {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 1.5rem;
    align-items: start;
  }

  @media (max-width: 1024px) {
    .planning-layout {
      grid-template-columns: 1fr;
    }
  }

  /* ── Left sidebar ── */
  .sidebar-title {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-heading);
    margin: 0 0 0.5rem;
  }

  .sidebar-desc {
    font-size: 0.8125rem;
    color: var(--text-muted);
    margin: 0 0 1rem;
  }

  .external-events {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .external-event {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.625rem;
    border-radius: 0.3125rem;
    font-size: 1rem;
    font-weight: 500;
    color: var(--text-heading);
    background: rgba(var(--primary-rgb), 0.04);
    transition: background 0.15s;
    cursor: default;
  }

  .external-event:hover {
    background: rgba(var(--primary-rgb), 0.08);
  }

  .external-event__dot {
    width: 0.875rem;
    height: 0.875rem;
    border-radius: 2px;
    flex-shrink: 0;
  }

  /* ── FullCalendar overrides (scoped) ── */
  /* Base styling handled by global .app-fullcalendar in app.css */
  /* Extra scoped overrides here */

  :global(.app-fullcalendar .fc-event) {
    cursor: pointer;
    font-size: 0.6875rem;
    font-family: 'Poppins', sans-serif;
  }

  :global(.app-fullcalendar .fc-daygrid-more-link) {
    color: var(--primary);
    font-size: 0.6875rem;
    font-weight: 600;
  }

  :global(.app-fullcalendar .fc-popover) {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 0.625rem;
    box-shadow: 0 8px 30px rgba(0,0,0,0.2);
  }

  :global(.app-fullcalendar .fc-popover-header) {
    background: var(--bg-input);
    color: var(--text-heading);
    padding: 0.5rem 0.75rem;
    font-size: 0.8125rem;
    font-weight: 600;
  }

  :global(.app-fullcalendar .fc-popover-body) {
    padding: 0.375rem;
  }

  :global(.app-fullcalendar .fc-timegrid-now-indicator-arrow) {
    border-color: var(--danger);
  }

  :global(.app-fullcalendar .fc-timegrid-now-indicator-line) {
    border-color: var(--danger);
  }

  /* ── Dialog form fields ── */
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    margin-bottom: 0.875rem;
  }

  .field span {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .field input, .field textarea, .field select {
    width: 100%;
    background: var(--bg-input);
    border: 1px solid var(--border-subtle);
    border-radius: 0.625rem;
    padding: 0.5rem 0.75rem;
    font-size: 0.8125rem;
    color: var(--text-primary);
    font-family: inherit;
  }

  .field input:focus, .field textarea:focus, .field select:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 0.25rem rgba(var(--primary-rgb), 0.15);
    outline: none;
  }

  .field-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }

  .checkbox-field {
    flex-direction: row;
    align-items: center;
    gap: 0.5rem;
  }

  .checkbox-field input {
    width: auto;
    accent-color: var(--primary);
  }

  .checkbox-field span {
    text-transform: none;
    font-weight: 500;
    color: var(--text-primary);
  }

  /* ── Type selector ── */
  .type-selector {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .type-option {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    border: 1px solid var(--border-subtle);
    border-radius: 0.5rem;
    background: transparent;
    color: var(--text-secondary);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
  }

  .type-option:hover {
    border-color: var(--type-color);
    color: var(--type-color);
  }

  .type-option.selected {
    background: var(--type-color);
    border-color: var(--type-color);
    color: #fff;
  }

  .type-emoji {
    font-size: 0.875rem;
  }

  .type-label {
    font-weight: 500;
  }
</style>
