<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../api/client.js';
  import { currentPage } from '../stores/navigation.js';
  import { Calendar } from '@fullcalendar/core';
  import dayGridPlugin from '@fullcalendar/daygrid';
  import timeGridPlugin from '@fullcalendar/timegrid';
  import interactionPlugin from '@fullcalendar/interaction';
  import listPlugin from '@fullcalendar/list';
  import {
    Plus, X, Trash2, Save, Calendar as CalendarIcon,
    Users, Wrench, Settings, Palmtree, Flag, MapPin,
    Clock, FileText, Link, ChevronDown, ListChecks
  } from 'lucide-svelte';

  // ---------------------------------------------------------------------------
  // Constants
  // ---------------------------------------------------------------------------
  const EVENT_TYPES = {
    meeting:      { label: 'R\u00e9union',      color: '#4B8BFF' },
    intervention: { label: 'Intervention',  color: '#F59E0B' },
    maintenance:  { label: 'Maintenance',   color: '#8B5CF6' },
    leave:        { label: 'Cong\u00e9',        color: '#22C55E' },
    milestone:    { label: 'Jalon',         color: '#EC4899' },
    other:        { label: 'Autre',         color: '#64748B' },
  };

  const EVENT_TYPE_ICONS = {
    meeting: Users,
    intervention: Wrench,
    maintenance: Settings,
    leave: Palmtree,
    milestone: Flag,
    other: MapPin,
  };

  const SIDEBAR_CATEGORIES = Object.entries(EVENT_TYPES).map(([key, t]) => ({
    key,
    label: t.label,
    color: t.color,
  }));

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  let events = [];
  let calendarTasks = [];
  let loading = false;

  // FullCalendar
  let calendarEl;
  let calendarInstance;

  // Dialog
  let showDialog = false;
  let editingEvent = null; // null = create, object = edit
  let form = defaultForm();

  // Open tasks for linking
  let openTasks = [];

  // Sidebar quick-create form
  let sidebarForm = { title: '', date: '', time: '', event_type: 'other' };

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

  function getEventColor(evt) {
    if (evt._type === 'task') return 'var(--info)';
    return EVENT_TYPES[evt.event_type]?.color || '#64748B';
  }

  // ---------------------------------------------------------------------------
  // API
  // ---------------------------------------------------------------------------
  async function fetchEvents() {
    if (!calendarInstance) return;
    loading = true;
    const view = calendarInstance.view;
    const start = toDateStr(view.activeStart);
    const end = toDateStr(view.activeEnd);
    try {
      const [evts, tasks] = await Promise.all([
        api.get(`/api/planning/events?start=${start}&end=${end}`),
        api.get(`/api/planning/tasks-for-calendar?start=${start}&end=${end}`),
      ]);
      events = evts;
      calendarTasks = tasks;
      renderCalendarEvents();
    } catch (e) {
      console.error('Failed to fetch planning data', e);
    } finally {
      loading = false;
    }
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
  // Dialog open helpers
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
  // Sidebar quick create
  // ---------------------------------------------------------------------------
  async function sidebarCreateEvent() {
    if (!sidebarForm.title.trim() || !sidebarForm.date) return;
    const payload = {
      title: sidebarForm.title,
      event_type: sidebarForm.event_type,
      date_start: sidebarForm.date,
      date_end: sidebarForm.date,
      all_day: !sidebarForm.time,
      time_start: sidebarForm.time || null,
      time_end: null,
      person: '',
      notes: '',
      task_id: null,
    };
    if (sidebarForm.time) {
      const [h, m] = sidebarForm.time.split(':').map(Number);
      payload.time_end = `${String(h + 1).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    }
    try {
      await api.post('/api/planning/events', payload);
      sidebarForm = { title: '', date: '', time: '', event_type: 'other' };
      await fetchEvents();
    } catch (e) {
      console.error('Failed to create event from sidebar', e);
    }
  }

  // ---------------------------------------------------------------------------
  // FullCalendar helpers
  // ---------------------------------------------------------------------------
  function renderCalendarEvents() {
    if (!calendarInstance) return;
    calendarInstance.removeAllEvents();

    // Add events
    for (const evt of events) {
      const color = EVENT_TYPES[evt.event_type]?.color || '#64748B';
      const typeLabel = EVENT_TYPES[evt.event_type]?.label || '';
      const calEvt = {
        id: `evt-${evt.id}`,
        title: evt.title,
        start: evt.all_day ? evt.date_start : `${evt.date_start}T${evt.time_start || '00:00'}`,
        end: evt.all_day
          ? (evt.date_end > evt.date_start ? addDay(evt.date_end) : undefined)
          : `${evt.date_end || evt.date_start}T${evt.time_end || '23:59'}`,
        allDay: evt.all_day,
        backgroundColor: color,
        borderColor: color,
        extendedProps: { ...evt, _type: 'event' },
      };
      calendarInstance.addEvent(calEvt);
    }

    // Add tasks
    for (const t of calendarTasks) {
      calendarInstance.addEvent({
        id: `task-${t.id}`,
        title: t.title,
        start: t.due_date,
        allDay: true,
        backgroundColor: 'var(--info)',
        borderColor: 'var(--info)',
        classNames: ['fc-task-event'],
        extendedProps: { ...t, _type: 'task' },
      });
    }
  }

  function addDay(dateStr) {
    const d = new Date(dateStr);
    d.setDate(d.getDate() + 1);
    return toDateStr(d);
  }

  // ---------------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------------
  onMount(() => {
    calendarInstance = new Calendar(calendarEl, {
      plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin, listPlugin],
      initialView: 'dayGridMonth',
      locale: 'fr',
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
      editable: true,
      droppable: true,
      selectable: true,
      dayMaxEvents: 3,
      eventTimeFormat: {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      },
      slotLabelFormat: {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      },
      firstDay: 1, // Monday
      height: '100%',
      nowIndicator: true,

      // Click on date cell
      dateClick: (info) => {
        if (info.view.type === 'timeGridWeek' || info.view.type === 'timeGridDay') {
          const timeStr = info.date.toTimeString().slice(0, 5);
          openNewEvent(toDateStr(info.date), timeStr);
        } else {
          openNewEvent(toDateStr(info.date));
        }
      },

      // Click on event
      eventClick: (info) => {
        const evt = info.event.extendedProps;
        openEditEvent(evt);
      },

      // Drag-drop event
      eventDrop: async (info) => {
        const evt = info.event.extendedProps;
        if (evt._type === 'task') {
          info.revert();
          return;
        }
        try {
          const newStart = toDateStr(info.event.start);
          const newEnd = info.event.end ? toDateStr(info.event.end) : newStart;
          await api.put(`/api/planning/events/${evt.id}`, {
            ...evt,
            date_start: newStart,
            date_end: newEnd,
            time_start: info.event.allDay ? null : info.event.start.toTimeString().slice(0, 5),
            time_end: info.event.allDay ? null : (info.event.end ? info.event.end.toTimeString().slice(0, 5) : null),
          });
          await fetchEvents();
        } catch (e) {
          info.revert();
          console.error('Failed to update event', e);
        }
      },

      // Resize event
      eventResize: async (info) => {
        const evt = info.event.extendedProps;
        if (evt._type === 'task') {
          info.revert();
          return;
        }
        try {
          const newStart = toDateStr(info.event.start);
          const newEnd = info.event.end ? toDateStr(info.event.end) : newStart;
          await api.put(`/api/planning/events/${evt.id}`, {
            ...evt,
            date_start: newStart,
            date_end: newEnd,
            time_start: info.event.allDay ? null : info.event.start.toTimeString().slice(0, 5),
            time_end: info.event.allDay ? null : (info.event.end ? info.event.end.toTimeString().slice(0, 5) : null),
          });
          await fetchEvents();
        } catch (e) {
          info.revert();
          console.error('Failed to resize event', e);
        }
      },

      // Re-fetch when view or date range changes
      datesSet: () => {
        fetchEvents();
      },
    });

    calendarInstance.render();
  });

  onDestroy(() => {
    if (calendarInstance) {
      calendarInstance.destroy();
    }
  });
</script>

<div class="planning-page">
  <!-- Left sidebar -->
  <aside class="planning-sidebar">
    <button class="btn-create" on:click={() => openNewEvent(toDateStr(new Date()))}>
      <Plus size={16} /> Cr\u00e9er un \u00e9v\u00e9nement
    </button>

    <!-- Quick create form -->
    <div class="sidebar-form">
      <h4 class="sidebar-heading">Cr\u00e9ation rapide</h4>
      <input
        type="text"
        class="sidebar-input"
        placeholder="Titre"
        bind:value={sidebarForm.title}
      />
      <input
        type="date"
        class="sidebar-input"
        bind:value={sidebarForm.date}
      />
      <input
        type="time"
        class="sidebar-input"
        bind:value={sidebarForm.time}
        placeholder="Heure (optionnel)"
      />
      <select class="sidebar-input" bind:value={sidebarForm.event_type}>
        {#each Object.entries(EVENT_TYPES) as [key, t]}
          <option value={key}>{t.label}</option>
        {/each}
      </select>
      <button
        class="btn-sidebar-create"
        on:click={sidebarCreateEvent}
        disabled={!sidebarForm.title.trim() || !sidebarForm.date}
      >
        <Plus size={14} /> Cr\u00e9er
      </button>
    </div>

    <!-- Category tags -->
    <div class="sidebar-categories">
      <h4 class="sidebar-heading">Cat\u00e9gories</h4>
      {#each SIDEBAR_CATEGORIES as cat}
        <div class="category-tag" style="--cat-color: {cat.color}">
          <span class="cat-dot"></span>
          <svelte:component this={EVENT_TYPE_ICONS[cat.key]} size={14} />
          <span class="cat-label">{cat.label}</span>
        </div>
      {/each}
      <div class="category-tag" style="--cat-color: var(--info)">
        <span class="cat-dot"></span>
        <ListChecks size={14} />
        <span class="cat-label">T\u00e2che</span>
      </div>
    </div>
  </aside>

  <!-- Calendar area -->
  <div class="planning-main">
    <div class="calendar-wrapper" bind:this={calendarEl}></div>
  </div>
</div>

<!-- Event dialog -->
{#if showDialog}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="dialog-overlay" on:click|self={() => showDialog = false}>
    <div class="dialog">
      <div class="dialog-header">
        <h3>{editingEvent ? 'Modifier l\'\u00e9v\u00e9nement' : 'Nouvel \u00e9v\u00e9nement'}</h3>
        <button class="dialog-close" on:click={() => showDialog = false}>
          <X size={18} />
        </button>
      </div>

      <label class="field">
        <span>Titre *</span>
        <input type="text" bind:value={form.title} placeholder="Titre de l'\u00e9v\u00e9nement" />
      </label>

      <!-- Event type selector with colored icons -->
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
              <svelte:component this={EVENT_TYPE_ICONS[key]} size={14} />
              <span class="type-label">{t.label}</span>
            </button>
          {/each}
        </div>
      </div>

      <label class="field">
        <span><Users size={12} /> Personne</span>
        <input type="text" bind:value={form.person} placeholder="Optionnel" />
      </label>

      <div class="field-row">
        <label class="field">
          <span>Date d\u00e9but</span>
          <input type="date" bind:value={form.date_start} />
        </label>
        <label class="field">
          <span>Date fin</span>
          <input type="date" bind:value={form.date_end} min={form.date_start} />
        </label>
      </div>

      <label class="field checkbox-field">
        <input type="checkbox" bind:checked={form.all_day} />
        <span>Journ\u00e9e enti\u00e8re</span>
      </label>

      {#if !form.all_day}
        <div class="field-row">
          <label class="field">
            <span><Clock size={12} /> Heure d\u00e9but</span>
            <input type="time" bind:value={form.time_start} />
          </label>
          <label class="field">
            <span><Clock size={12} /> Heure fin</span>
            <input type="time" bind:value={form.time_end} />
          </label>
        </div>
      {/if}

      <label class="field">
        <span><FileText size={12} /> Notes</span>
        <textarea bind:value={form.notes} rows="3" placeholder="Notes optionnelles"></textarea>
      </label>

      <label class="field">
        <span><Link size={12} /> Lier \u00e0 une t\u00e2che</span>
        <select bind:value={form.task_id}>
          <option value={null}>-- Aucune --</option>
          {#each openTasks as t}
            <option value={t.id}>{t.title}</option>
          {/each}
        </select>
      </label>

      <div class="dialog-actions">
        {#if editingEvent}
          <button class="btn-delete" on:click={deleteEvent}>
            <Trash2 size={14} />
            Supprimer
          </button>
        {/if}
        <div class="spacer"></div>
        <button class="btn-cancel" on:click={() => showDialog = false}>Annuler</button>
        <button class="btn-save" on:click={saveEvent} disabled={!form.title.trim()}>
          <Save size={14} />
          {editingEvent ? 'Enregistrer' : 'Cr\u00e9er'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  /* =========================================================================
     Planning Page – FullCalendar + Sidebar layout
     ========================================================================= */
  .planning-page {
    animation: fadeIn 0.35s ease-out;
    display: flex;
    height: calc(100vh - 56px);
    overflow: hidden;
    gap: 0;
  }

  /* =========================================================================
     Sidebar
     ========================================================================= */
  .planning-sidebar {
    width: 300px;
    flex-shrink: 0;
    background: var(--bg-card);
    border-right: 1px solid var(--border-subtle);
    padding: 20px 16px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    overflow-y: auto;
  }

  .btn-create {
    width: 100%;
    background: var(--primary);
    border: none;
    border-radius: 10px;
    color: #fff;
    font-size: 14px;
    font-weight: 600;
    padding: 12px 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    font-family: inherit;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-shadow: 0 4px 14px rgba(var(--primary-rgb), 0.35);
  }
  .btn-create:hover {
    filter: brightness(1.15);
    box-shadow: 0 6px 20px rgba(var(--primary-rgb), 0.45);
    transform: translateY(-1px);
  }
  .btn-create:active {
    transform: translateY(0);
  }

  .sidebar-heading {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-muted);
    margin: 0 0 10px;
  }

  .sidebar-form {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .sidebar-input {
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 13px;
    padding: 8px 10px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.15s;
    width: 100%;
  }
  .sidebar-input:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 0.15);
  }

  .btn-sidebar-create {
    background: rgba(var(--primary-rgb), 0.15);
    border: 1px solid rgba(var(--primary-rgb), 0.3);
    border-radius: 8px;
    color: var(--primary);
    font-size: 13px;
    font-weight: 600;
    padding: 8px 12px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }
  .btn-sidebar-create:hover:not(:disabled) {
    background: rgba(var(--primary-rgb), 0.25);
    border-color: var(--primary);
  }
  .btn-sidebar-create:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .sidebar-categories {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .category-tag {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    font-size: 13px;
    color: var(--text-secondary);
    cursor: default;
    transition: background 0.15s;
  }
  .category-tag:hover {
    background: var(--bg-hover);
  }

  .cat-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--cat-color);
    flex-shrink: 0;
  }

  .cat-label {
    font-weight: 500;
  }

  /* =========================================================================
     Calendar Main Area
     ========================================================================= */
  .planning-main {
    flex: 1;
    min-width: 0;
    padding: 16px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .calendar-wrapper {
    flex: 1;
    min-height: 0;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 12px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
    overflow: hidden;
  }

  /* Task events in calendar */
  :global(.fc-task-event) {
    border-style: dashed !important;
    opacity: 0.85;
  }
  :global(.fc-task-event:hover) {
    opacity: 1;
  }

  /* =========================================================================
     Dialog - Glass Morphism
     ========================================================================= */
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    animation: fadeInOverlay 0.2s ease-out;
  }
  @keyframes fadeInOverlay {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .dialog {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 24px 28px;
    width: 500px;
    max-width: 95vw;
    max-height: 90vh;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5), 0 0 0 1px var(--overlay-white-5);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    animation: dialogSlideIn 0.25s ease-out;
  }
  @keyframes dialogSlideIn {
    from {
      opacity: 0;
      transform: translateY(12px) scale(0.97);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .dialog-header h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.2px;
  }
  .dialog-close {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
  }
  .dialog-close:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  /* Event type selector */
  .type-selector {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 4px;
  }
  .type-option {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 6px 10px;
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    background: transparent;
    color: var(--text-secondary);
    font-size: 12px;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .type-option:hover {
    border-color: var(--type-color);
    background: color-mix(in srgb, var(--type-color) 8%, transparent);
    color: var(--text-primary);
  }
  .type-option.selected {
    border-color: var(--type-color);
    background: color-mix(in srgb, var(--type-color) 15%, transparent);
    color: var(--text-primary);
    box-shadow: 0 0 8px color-mix(in srgb, var(--type-color) 20%, transparent);
  }
  .type-label {
    font-weight: 500;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .field > span {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    letter-spacing: 0.2px;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .field input[type="text"],
  .field input[type="date"],
  .field input[type="time"],
  .field select,
  .field textarea {
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    color: var(--text-primary);
    font-size: 13px;
    padding: 9px 12px;
    font-family: inherit;
    outline: none;
    transition: all 0.2s ease;
  }
  .field input:focus,
  .field select:focus,
  .field textarea:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 0.15);
  }
  .field textarea {
    resize: vertical;
  }

  .field-row {
    display: flex;
    gap: 12px;
  }
  .field-row .field {
    flex: 1;
  }

  .checkbox-field {
    flex-direction: row;
    align-items: center;
    gap: 8px;
  }
  .checkbox-field input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: var(--primary);
  }

  .dialog-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
    padding-top: 12px;
    border-top: 1px solid var(--border-subtle);
  }
  .spacer {
    flex: 1;
  }

  .btn-delete {
    background: transparent;
    border: 1px solid rgba(var(--danger-rgb), 0.4);
    border-radius: 10px;
    color: var(--danger);
    font-size: 13px;
    padding: 8px 14px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 500;
  }
  .btn-delete:hover {
    background: rgba(var(--danger-rgb), 0.1);
    border-color: rgba(var(--danger-rgb), 0.6);
  }

  .btn-cancel {
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    color: var(--text-secondary);
    font-size: 13px;
    padding: 8px 16px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
    font-weight: 500;
  }
  .btn-cancel:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
    border-color: var(--border-hover);
  }

  .btn-save {
    background: var(--primary);
    border: none;
    border-radius: 10px;
    color: #fff;
    font-size: 13px;
    font-weight: 700;
    padding: 9px 22px;
    cursor: pointer;
    transition: all 0.2s ease;
    font-family: inherit;
    box-shadow: 0 2px 8px rgba(var(--primary-rgb), 0.3);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .btn-save:hover:not(:disabled) {
    filter: brightness(1.15);
    box-shadow: 0 4px 14px rgba(var(--primary-rgb), 0.4);
    transform: translateY(-1px);
  }
  .btn-save:active:not(:disabled) {
    transform: translateY(0);
  }
  .btn-save:disabled {
    opacity: 0.35;
    cursor: not-allowed;
    box-shadow: none;
  }

  /* =========================================================================
     Responsive
     ========================================================================= */
  @media (max-width: 900px) {
    .planning-page {
      flex-direction: column;
      height: auto;
    }
    .planning-sidebar {
      width: 100%;
      border-right: none;
      border-bottom: 1px solid var(--border-subtle);
      max-height: 250px;
      flex-direction: row;
      flex-wrap: wrap;
      gap: 12px;
      padding: 12px;
    }
    .sidebar-form {
      flex-direction: row;
      flex-wrap: wrap;
      gap: 8px;
    }
    .sidebar-input {
      flex: 1;
      min-width: 120px;
    }
    .sidebar-categories {
      flex-direction: row;
      flex-wrap: wrap;
      gap: 6px;
    }
    .planning-main {
      min-height: 500px;
    }
  }
</style>
