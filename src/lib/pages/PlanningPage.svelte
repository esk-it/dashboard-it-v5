<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../api/client.js';
  import { currentPage } from '../stores/navigation.js';
  import { Calendar } from '@fullcalendar/core';
  import dayGridPlugin from '@fullcalendar/daygrid';
  import timeGridPlugin from '@fullcalendar/timegrid';
  import listPlugin from '@fullcalendar/list';
  import interactionPlugin, { Draggable } from '@fullcalendar/interaction';

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
  let externalEventsEl;
  let calendar;
  let draggable;
  let events = [];
  let calendarTasks = [];

  // Dialog
  let showDialog = false;
  let editingEvent = null;
  let form = defaultForm();
  let openTasks = [];

  // Google Calendar sync
  let gcalConnected = false;
  let gcalSyncing = false;
  let gcalLastSync = null;

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
        editable: true,
        durationEditable: true,
        startEditable: true,
        extendedProps: { ...evt, _type: 'event' },
      };
    });

    // Add tasks (not editable)
    const fcTasks = calendarTasks.map(t => ({
      id: `task-${t.id}`,
      title: `\u2705 ${t.title}`,
      start: t.due_date,
      allDay: true,
      backgroundColor: '#4B8BFF',
      borderColor: '#4B8BFF',
      textColor: '#fff',
      editable: false,
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
  // Google Calendar
  // ---------------------------------------------------------------------------
  async function checkGcalConnection() {
    try {
      const cfg = await api.get('/api/google-calendar/config');
      gcalConnected = cfg.connected || false;
      gcalLastSync = cfg.last_sync || null;
    } catch {
      gcalConnected = false;
    }
  }

  async function syncGcal() {
    gcalSyncing = true;
    try {
      await api.post('/api/google-calendar/sync');
      await fetchEvents();
      await checkGcalConnection();
    } catch (e) {
      console.error('Google Calendar sync failed', e);
    }
    gcalSyncing = false;
  }

  // ---------------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------------
  onMount(() => {
    checkGcalConnection();
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
      height: '100%',
      expandRows: true,
      dayMaxEvents: 3,
      weekNumbers: true,
      navLinks: true,
      editable: true,
      eventResizableFromStart: true,
      droppable: true,
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

      // Drag & drop from sidebar — create event directly (no dialog)
      drop: async (info) => {
        const eventType = info.draggedEl.dataset.eventType || 'other';
        const t = EVENT_TYPES[eventType];
        const dateStr = toDateStr(info.date);
        try {
          await api.post('/api/planning/events', {
            title: t ? t.label : 'Evenement',
            event_type: eventType,
            date_start: dateStr,
            date_end: dateStr,
            all_day: true,
            time_start: null,
            time_end: null,
            person: '',
            notes: '',
            task_id: null,
          });
          await fetchEvents();
        } catch (e) {
          console.error('Failed to create event from drop', e);
        }
      },

      // Drag existing event to new date
      eventDrop: async (info) => {
        const props = info.event.extendedProps;
        if (props._type === 'task') { info.revert(); return; }
        const start = info.event.start;
        const end = info.event.end || info.event.start;
        const isAllDay = info.event.allDay;
        const newDateStart = toDateStr(start);
        const newDateEnd = toDateStr(end.getTime() > start.getTime() && isAllDay ? new Date(end.getTime() - 86400000) : end);
        const payload = { date_start: newDateStart, date_end: newDateEnd };
        if (!isAllDay) {
          payload.time_start = `${String(start.getHours()).padStart(2,'0')}:${String(start.getMinutes()).padStart(2,'0')}`;
          payload.time_end = end ? `${String(end.getHours()).padStart(2,'0')}:${String(end.getMinutes()).padStart(2,'0')}` : null;
        }
        try {
          await api.put(`/api/planning/events/${props.id}`, payload);
          // Update extendedProps so click shows correct dates
          info.event.setExtendedProp('date_start', newDateStart);
          info.event.setExtendedProp('date_end', newDateEnd);
          if (payload.time_start !== undefined) info.event.setExtendedProp('time_start', payload.time_start);
          if (payload.time_end !== undefined) info.event.setExtendedProp('time_end', payload.time_end);
        } catch { info.revert(); }
      },

      // Resize event (drag edges)
      eventResize: async (info) => {
        const props = info.event.extendedProps;
        if (props._type === 'task') { info.revert(); return; }
        const start = info.event.start;
        const end = info.event.end || info.event.start;
        const isAllDay = info.event.allDay;
        const newDateStart = toDateStr(start);
        const newDateEnd = toDateStr(isAllDay ? new Date(end.getTime() - 86400000) : end);
        const payload = { date_start: newDateStart, date_end: newDateEnd };
        if (!isAllDay) {
          payload.time_start = `${String(start.getHours()).padStart(2,'0')}:${String(start.getMinutes()).padStart(2,'0')}`;
          payload.time_end = `${String(end.getHours()).padStart(2,'0')}:${String(end.getMinutes()).padStart(2,'0')}`;
        }
        try {
          await api.put(`/api/planning/events/${props.id}`, payload);
          // Update extendedProps so click shows correct dates
          info.event.setExtendedProp('date_start', newDateStart);
          info.event.setExtendedProp('date_end', newDateEnd);
          if (payload.time_start !== undefined) info.event.setExtendedProp('time_start', payload.time_start);
          if (payload.time_end !== undefined) info.event.setExtendedProp('time_end', payload.time_end);
        } catch { info.revert(); }
      },
    });

    calendar.render();

    // Initialize external events draggable
    if (externalEventsEl) {
      draggable = new Draggable(externalEventsEl, {
        itemSelector: '.external-event',
        eventData: (eventEl) => {
          const eventType = eventEl.dataset.eventType || 'other';
          const t = EVENT_TYPES[eventType];
          return {
            title: t ? t.label : eventEl.textContent.trim(),
            backgroundColor: t ? t.color : '#64748B',
            borderColor: t ? t.color : '#64748B',
            create: false, // don't auto-create — we handle in drop callback
          };
        },
      });
    }
  });

  onDestroy(() => {
    if (draggable) draggable.destroy();
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
          <p class="sidebar-desc">Glissez-deposez un type dans le calendrier ou cliquez pour creer</p>

          <div class="external-events" bind:this={externalEventsEl}>
            {#each Object.entries(EVENT_TYPES) as [key, t]}
              <div class="external-event" data-event-type={key} style="--evt-color:{t.color}">
                <span class="external-event__dot" style="background:{t.color}"></span>
                <span>{t.label}</span>
              </div>
            {/each}
          </div>

          <button class="ya-btn ya-btn--primary" style="width:100%;margin-top:1.5rem" on:click={() => openNewEvent(toDateStr(new Date()))}>
            + Creer un evenement
          </button>

          {#if gcalConnected}
            <div class="gcal-sync" style="margin-top:1rem">
              <button
                class="ya-btn ya-btn--ghost gcal-sync-btn"
                style="width:100%;display:flex;align-items:center;justify-content:center;gap:0.5rem"
                on:click={syncGcal}
                disabled={gcalSyncing}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 12a10 10 0 0118-6M22 12a10 10 0 01-18 6"/></svg>
                {gcalSyncing ? 'Synchronisation...' : 'Sync Google Calendar'}
              </button>
              {#if gcalLastSync}
                <p class="gcal-last-sync">Dernier sync : {new Date(gcalLastSync).toLocaleString('fr-FR')}</p>
              {/if}
            </div>
          {/if}
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
    /* Fill available viewport height */
    min-height: calc(100vh - 140px);
    display: flex;
    flex-direction: column;
  }

  /* ── 2-column layout (YashAdmin calendar style) ── */
  .planning-layout {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 1.5rem;
    align-items: stretch;
    flex: 1;
  }

  .planning-main {
    display: flex;
    flex-direction: column;
  }

  .planning-main > .ya-page-card {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .planning-main > .ya-page-card > .ya-page-card__body {
    flex: 1;
  }

  @media (max-width: 1024px) {
    .planning-layout {
      grid-template-columns: 1fr;
    }
    .planning-page {
      min-height: auto;
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
    cursor: grab;
    user-select: none;
  }

  .external-event:hover {
    opacity: 0.85;
  }

  .external-event:active {
    cursor: grabbing;
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

  /* ── Google Calendar sync ── */
  .gcal-sync-btn:disabled {
    opacity: 0.6;
    cursor: wait;
  }

  .gcal-last-sync {
    font-size: 0.6875rem;
    color: var(--text-muted);
    text-align: center;
    margin: 0.375rem 0 0;
  }
</style>
