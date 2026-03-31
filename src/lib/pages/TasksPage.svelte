<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import { api } from '../api/client.js';
  import { success, error as toastError } from '../stores/toast.js';
  import {
    Plus, Search, ClipboardList, LayoutGrid, BarChart3,
    Pencil, Trash2, CheckSquare, Square, Calendar,
    RefreshCw, ChevronDown, X, FileDown, Building2, Globe,
    ArrowDown, Equal, AlertTriangle, ListChecks, StickyNote,
    Clock, CheckCircle2, AlertCircle, Timer, CircleDot,
    PlayCircle, TestTube, Pause, Flag
  } from 'lucide-svelte';

  // ── Constants ──────────────────────────────────────────────
  const SITES = [
    { value: '', label: 'Tous sites', icon: null },
    { value: 'NDK', label: 'NDK', icon: null },
    { value: 'NDE', label: 'NDE', icon: null },
    { value: 'SU', label: 'SU', icon: null },
    { value: 'Global', label: 'Global', icon: null },
  ];

  const PRIORITIES = [
    { value: 1, label: 'Basse', color: '#22C55E', icon: 'down' },
    { value: 2, label: 'Normale', color: '#3B82F6', icon: 'equal' },
    { value: 3, label: 'Urgente', color: '#EF4444', icon: 'alert' },
  ];

  const RECURRENCES = [
    { value: '', label: 'Aucune' },
    { value: 'daily', label: 'Quotidienne' },
    { value: 'weekly', label: 'Hebdomadaire' },
    { value: 'biweekly', label: 'Bimensuelle' },
    { value: 'monthly', label: 'Mensuelle' },
  ];

  const QUICK_FILTERS = [
    { key: 'all', label: 'Tout' },
    { key: 'overdue', label: 'En retard' },
    { key: 'today', label: "Aujourd'hui" },
    { key: 'week', label: 'Semaine' },
    { key: 'nodate', label: 'Sans date' },
  ];

  // Status definitions for KPI badges
  const STATUS_DEFS = [
    { key: 'not_started', label: 'Non d\u00e9marr\u00e9', colorVar: 'primary', colorVal: 'var(--primary)' },
    { key: 'in_progress', label: 'En cours', colorVar: 'purple', colorVal: '#BB6BD9' },
    { key: 'testing', label: 'Test', colorVar: 'warning', colorVal: 'var(--warning)' },
    { key: 'waiting', label: 'En attente', colorVar: 'danger', colorVal: 'var(--danger)' },
    { key: 'done', label: 'Termin\u00e9', colorVar: 'success', colorVal: 'var(--success)' },
    { key: 'overdue', label: 'En retard', colorVar: 'info', colorVal: 'var(--info)' },
  ];

  // ── State ──────────────────────────────────────────────────
  let tasks = [];
  let categories = [];
  let loading = true;

  // Filters
  let filterStatus = 'all';
  let filterSite = '';
  let searchQuery = '';
  let quickFilter = 'all';
  let searchDebounceTimer;

  // View
  let viewMode = 'list'; // 'list' | 'kanban' | 'stats'
  let expandedTaskId = null;

  // Task dialog
  let showTaskDialog = false;
  let editingTask = null;
  let dialogForm = resetDialogForm();
  let dialogNoDueDate = true;

  // Template modal
  let showTemplateModal = false;
  let templates = [];
  let selectedTemplateId = null;
  let templateForm = resetTemplateForm();

  // Checklists cache
  let checklistsCache = {};
  let newChecklistText = {};

  // ── Helpers ────────────────────────────────────────────────
  function resetDialogForm() {
    return { title: '', site: '', category: '', priority: 2, due_date: '', recurrence: '', notes: '' };
  }

  function resetTemplateForm() {
    return { name: '', title: '', category: '', priority: 2, notes: '', site: '', recurrence: '', checklist_json: '[]' };
  }

  function todayStr() {
    return new Date().toISOString().slice(0, 10);
  }

  function endOfWeekStr() {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    return d.toISOString().slice(0, 10);
  }

  function getDueStatus(task) {
    if (task.done) return 'done';
    if (!task.due_date) return 'nodate';
    const today = todayStr();
    const weekEnd = endOfWeekStr();
    if (task.due_date < today) return 'overdue';
    if (task.due_date === today) return 'today';
    if (task.due_date <= weekEnd) return 'week';
    return 'future';
  }

  function getDueLabel(status) {
    switch (status) {
      case 'overdue': return 'En retard';
      case 'today': return "Aujourd'hui";
      case 'week': return 'Bient\u00f4t';
      case 'future': return '\u00c0 venir';
      case 'nodate': return 'Sans date';
      case 'done': return 'Termin\u00e9e';
      default: return '';
    }
  }

  function getDueColor(status) {
    switch (status) {
      case 'overdue': return 'var(--danger)';
      case 'today': return 'var(--warning)';
      case 'week': return 'var(--info)';
      case 'future': return 'var(--text-muted)';
      case 'nodate': return 'var(--text-muted)';
      default: return 'var(--text-muted)';
    }
  }

  function getPriority(val) {
    return PRIORITIES.find(p => p.value === val) || PRIORITIES[1];
  }

  function getPriorityClass(val) {
    if (val === 3) return 'badge-danger';
    if (val === 1) return 'badge-primary';
    return 'badge-warning';
  }

  function getStatusBadgeClass(status) {
    switch (status) {
      case 'overdue': return 'badge-danger';
      case 'today': return 'badge-warning';
      case 'week': return 'badge-info';
      case 'future': return 'badge-muted';
      case 'nodate': return 'badge-muted';
      case 'done': return 'badge-success';
      default: return 'badge-muted';
    }
  }

  // ── KPI badge counts ────────────────────────────────────────
  $: kpiCounts = computeKpiCounts(tasks);

  function computeKpiCounts(allTasks) {
    const today = todayStr();
    const notStarted = allTasks.filter(t => !t.done && !t.due_date).length;
    const inProgress = allTasks.filter(t => !t.done && t.due_date && t.due_date >= today).length;
    const testing = 0; // No explicit status field, placeholder
    const waiting = 0; // No explicit status field, placeholder
    const done = allTasks.filter(t => t.done).length;
    const overdue = allTasks.filter(t => !t.done && t.due_date && t.due_date < today).length;
    return [notStarted, inProgress, testing, waiting, done, overdue];
  }

  // ── Computed / reactive ────────────────────────────────────
  $: filteredTasks = applyFilters(tasks, filterStatus, filterSite, searchQuery, quickFilter);

  function applyFilters(list, status, site, search, qf) {
    let result = [...list];

    if (status === 'open') result = result.filter(t => !t.done);
    else if (status === 'done') result = result.filter(t => t.done);

    if (site) result = result.filter(t => t.site === site);

    if (search) {
      const s = search.toLowerCase();
      result = result.filter(t => t.title.toLowerCase().includes(s) || (t.notes && t.notes.toLowerCase().includes(s)));
    }

    if (qf === 'overdue') result = result.filter(t => getDueStatus(t) === 'overdue');
    else if (qf === 'today') result = result.filter(t => getDueStatus(t) === 'today');
    else if (qf === 'week') result = result.filter(t => ['today', 'week'].includes(getDueStatus(t)));
    else if (qf === 'nodate') result = result.filter(t => !t.due_date && !t.done);

    return result;
  }

  $: sections = buildSections(filteredTasks);

  function buildSections(list) {
    const groups = {
      overdue: { label: 'EN RETARD', color: 'var(--danger)', tasks: [] },
      today: { label: "AUJOURD'HUI", color: 'var(--warning)', tasks: [] },
      week: { label: 'CETTE SEMAINE', color: 'var(--info)', tasks: [] },
      future: { label: '\u00c0 VENIR', color: 'var(--text-muted)', tasks: [] },
      nodate: { label: 'SANS \u00c9CH\u00c9ANCE', color: 'var(--text-muted)', tasks: [] },
      done: { label: 'TERMIN\u00c9ES', color: 'var(--success)', tasks: [] },
    };

    for (const t of list) {
      const s = getDueStatus(t);
      if (groups[s]) groups[s].tasks.push(t);
    }

    return Object.entries(groups).filter(([, g]) => g.tasks.length > 0);
  }

  // Stats
  $: openCount = tasks.filter(t => !t.done).length;
  $: overdueCount = tasks.filter(t => !t.done && t.due_date && t.due_date < todayStr()).length;
  $: weekCount = tasks.filter(t => !t.done && t.due_date && t.due_date >= todayStr() && t.due_date <= endOfWeekStr()).length;
  $: doneCount = tasks.filter(t => t.done).length;
  $: totalCount = tasks.length;
  $: progressPct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0;

  // Kanban
  $: kanbanColumns = buildKanban(filteredTasks);

  // Stats computed from all tasks (not filtered)
  $: taskStats = computeStats(tasks);

  function computeStats(allTasks) {
    const today = new Date().toISOString().slice(0, 10);
    const total = allTasks.length;
    const done = allTasks.filter(t => t.done).length;
    const open = total - done;
    const overdue = allTasks.filter(t => !t.done && t.due_date && t.due_date < today).length;
    const completionRate = total > 0 ? Math.round(done / total * 100) : 0;

    // By category
    const byCat = {};
    for (const t of allTasks) {
      const cat = t.category || 'Sans cat\u00e9gorie';
      if (!byCat[cat]) byCat[cat] = { total: 0, done: 0, open: 0 };
      byCat[cat].total++;
      if (t.done) byCat[cat].done++;
      else byCat[cat].open++;
    }

    // By priority
    const byPrio = [0, 0, 0]; // [basse, normale, urgente]
    for (const t of allTasks.filter(t => !t.done)) {
      byPrio[(t.priority || 2) - 1]++;
    }

    // By site
    const bySite = {};
    for (const t of allTasks) {
      const site = t.site || 'Sans site';
      if (!bySite[site]) bySite[site] = { total: 0, done: 0, open: 0 };
      bySite[site].total++;
      if (t.done) bySite[site].done++;
      else bySite[site].open++;
    }

    // Completion over last 7 days
    const weekData = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const ds = d.toISOString().slice(0, 10);
      const dayLabel = d.toLocaleDateString('fr-FR', { weekday: 'short' });
      const created = allTasks.filter(t => (t.created_at || '').slice(0, 10) === ds).length;
      const completed = allTasks.filter(t => t.done && (t.created_at || '').slice(0, 10) === ds).length;
      weekData.push({ label: dayLabel, created, completed });
    }

    return { total, done, open, overdue, completionRate, byCat, byPrio, bySite, weekData };
  }

  function buildKanban(list) {
    const open = list.filter(t => !t.done);
    return [
      { priority: 3, label: 'Urgente', color: 'var(--danger)', tasks: open.filter(t => t.priority === 3) },
      { priority: 2, label: 'Normale', color: 'var(--info)', tasks: open.filter(t => t.priority === 2) },
      { priority: 1, label: 'Basse', color: 'var(--success)', tasks: open.filter(t => t.priority === 1) },
    ];
  }

  // ── API calls ──────────────────────────────────────────────
  async function fetchTasks() {
    try {
      tasks = await api.get('/api/tasks');
    } catch (e) {
      toastError('Erreur chargement t\u00e2ches');
    }
    loading = false;
  }

  async function fetchCategories() {
    try {
      categories = await api.get('/api/tasks/categories');
    } catch (_) {}
  }

  async function toggleDone(task) {
    try {
      const updated = await api.patch(`/api/tasks/${task.id}/done`);
      tasks = tasks.map(t => t.id === updated.id ? updated : t);
      success(updated.done ? 'T\u00e2che termin\u00e9e' : 'T\u00e2che r\u00e9ouverte');
    } catch (e) {
      toastError('Erreur');
    }
  }

  async function deleteTask(task) {
    if (!confirm(`Supprimer \u00ab ${task.title} \u00bb ?`)) return;
    try {
      await api.delete(`/api/tasks/${task.id}`);
      tasks = tasks.filter(t => t.id !== task.id);
      if (expandedTaskId === task.id) expandedTaskId = null;
      success('T\u00e2che supprim\u00e9e');
    } catch (e) {
      toastError('Erreur suppression');
    }
  }

  async function saveTask() {
    const body = {
      title: dialogForm.title,
      site: dialogForm.site,
      category: dialogForm.category,
      priority: dialogForm.priority,
      due_date: dialogNoDueDate ? null : dialogForm.due_date || null,
      recurrence: dialogForm.recurrence,
      notes: dialogForm.notes,
    };

    try {
      if (editingTask) {
        const updated = await api.put(`/api/tasks/${editingTask.id}`, body);
        tasks = tasks.map(t => t.id === updated.id ? updated : t);
        success('T\u00e2che modifi\u00e9e');
      } else {
        const created = await api.post('/api/tasks', body);
        tasks = [...tasks, created];
        success('T\u00e2che cr\u00e9\u00e9e');
      }
      closeTaskDialog();
    } catch (e) {
      toastError('Erreur sauvegarde');
    }
  }

  // ── Checklist ──────────────────────────────────────────────
  async function loadChecklist(taskId) {
    try {
      checklistsCache[taskId] = await api.get(`/api/tasks/${taskId}/checklist`);
      checklistsCache = checklistsCache;
    } catch (_) {}
  }

  async function addChecklistItem(taskId) {
    const text = (newChecklistText[taskId] || '').trim();
    if (!text) return;
    try {
      const items = checklistsCache[taskId] || [];
      const item = await api.post(`/api/tasks/${taskId}/checklist`, { text, sort_order: items.length });
      checklistsCache[taskId] = [...items, item];
      checklistsCache = checklistsCache;
      newChecklistText[taskId] = '';
      newChecklistText = newChecklistText;
    } catch (_) {
      toastError('Erreur ajout');
    }
  }

  async function toggleChecklistItem(taskId, item) {
    try {
      const updated = await api.patch(`/api/tasks/checklist/${item.id}/toggle`);
      checklistsCache[taskId] = (checklistsCache[taskId] || []).map(i => i.id === updated.id ? updated : i);
      checklistsCache = checklistsCache;
    } catch (_) {}
  }

  async function deleteChecklistItem(taskId, itemId) {
    try {
      await api.delete(`/api/tasks/checklist/${itemId}`);
      checklistsCache[taskId] = (checklistsCache[taskId] || []).filter(i => i.id !== itemId);
      checklistsCache = checklistsCache;
    } catch (_) {}
  }

  function getChecklistProgress(taskId) {
    const items = checklistsCache[taskId];
    if (!items || items.length === 0) return null;
    const done = items.filter(i => i.done).length;
    return { done, total: items.length };
  }

  // ── Dialog management ──────────────────────────────────────
  function openCreateDialog() {
    editingTask = null;
    dialogForm = resetDialogForm();
    dialogNoDueDate = true;
    showTaskDialog = true;
  }

  function openEditDialog(task) {
    editingTask = task;
    dialogForm = {
      title: task.title,
      site: task.site || '',
      category: task.category || '',
      priority: task.priority,
      due_date: task.due_date || '',
      recurrence: task.recurrence || '',
      notes: task.notes || '',
    };
    dialogNoDueDate = !task.due_date;
    showTaskDialog = true;
  }

  function closeTaskDialog() {
    showTaskDialog = false;
    editingTask = null;
  }

  // ── Expand/collapse ────────────────────────────────────────
  function toggleExpand(taskId) {
    if (expandedTaskId === taskId) {
      expandedTaskId = null;
    } else {
      expandedTaskId = taskId;
      if (!checklistsCache[taskId]) loadChecklist(taskId);
    }
  }

  // ── Notes inline edit ──────────────────────────────────────
  let editingNotesId = null;
  let editingNotesText = '';

  function startEditNotes(task) {
    editingNotesId = task.id;
    editingNotesText = task.notes || '';
  }

  async function saveNotes(task) {
    try {
      const updated = await api.put(`/api/tasks/${task.id}`, {
        title: task.title, site: task.site, category: task.category,
        priority: task.priority, due_date: task.due_date,
        recurrence: task.recurrence, notes: editingNotesText,
      });
      tasks = tasks.map(t => t.id === updated.id ? updated : t);
      editingNotesId = null;
      success('Notes sauvegard\u00e9es');
    } catch (_) {
      toastError('Erreur');
    }
  }

  function cancelEditNotes() {
    editingNotesId = null;
  }

  // ── Templates ──────────────────────────────────────────────
  async function fetchTemplates() {
    try {
      templates = await api.get('/api/tasks/templates');
    } catch (_) {}
  }

  function openTemplateModal() {
    fetchTemplates();
    selectedTemplateId = null;
    templateForm = resetTemplateForm();
    showTemplateModal = true;
  }

  function closeTemplateModal() {
    showTemplateModal = false;
  }

  function selectTemplate(t) {
    selectedTemplateId = t.id;
    templateForm = {
      name: t.name,
      title: t.title,
      category: t.category,
      priority: t.priority,
      notes: t.notes,
      site: t.site,
      recurrence: t.recurrence,
      checklist_json: t.checklist_json,
    };
  }

  async function saveTemplate() {
    if (!templateForm.name.trim()) return;
    try {
      const created = await api.post('/api/tasks/templates', templateForm);
      templates = [...templates, created];
      selectedTemplateId = created.id;
      success('Template cr\u00e9\u00e9');
    } catch (_) {
      toastError('Erreur');
    }
  }

  async function deleteTemplate(id) {
    try {
      await api.delete(`/api/tasks/templates/${id}`);
      templates = templates.filter(t => t.id !== id);
      if (selectedTemplateId === id) {
        selectedTemplateId = null;
        templateForm = resetTemplateForm();
      }
      success('Template supprim\u00e9');
    } catch (_) {}
  }

  async function useTemplate(id) {
    try {
      const created = await api.post(`/api/tasks/templates/${id}/use`, {});
      tasks = [...tasks, created];
      success('T\u00e2che cr\u00e9\u00e9e depuis template');
      closeTemplateModal();
    } catch (_) {
      toastError('Erreur');
    }
  }

  // ── Search debounce ────────────────────────────────────────
  function onSearchInput(e) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      searchQuery = e.target.value;
    }, 250);
  }

  // ── Lifecycle ──────────────────────────────────────────────
  onMount(() => {
    fetchTasks();
    fetchCategories();
  });

  onDestroy(() => {
    clearTimeout(searchDebounceTimer);
  });
</script>

<div class="tasks-page">
  <!-- ── KPI Badge Row ───────────────────────────────────── -->
  <div class="kpi-badge-row">
    {#each STATUS_DEFS as def, i}
      <div class="kpi-badge" style="--kpi-color: {def.colorVal}">
        <span class="kpi-count">{kpiCounts[i]}</span>
        <span class="kpi-label">{def.label}</span>
      </div>
    {/each}
  </div>

  <!-- Progress bar -->
  <div class="progress-wrapper">
    <div class="progress-bar">
      <div class="progress-fill" style="width: {progressPct}%"></div>
    </div>
    <span class="progress-label">{progressPct}% compl\u00e9t\u00e9</span>
  </div>

  <!-- ── Action bar ─────────────────────────────────────── -->
  <div class="action-bar">
    <div class="action-left">
      <div class="view-segmented">
        <button class="vseg" class:vseg-active={viewMode === 'list'} on:click={() => viewMode = 'list'}>
          <ClipboardList size={14} /> Liste
        </button>
        <button class="vseg" class:vseg-active={viewMode === 'kanban'} on:click={() => viewMode = 'kanban'}>
          <LayoutGrid size={14} /> Kanban
        </button>
        <button class="vseg" class:vseg-active={viewMode === 'stats'} on:click={() => viewMode = 'stats'}>
          <BarChart3 size={14} /> Stats
        </button>
      </div>
      <button class="btn-ghost" on:click={openTemplateModal}>
        <ListChecks size={14} /> Templates
      </button>
      <button class="btn-primary" on:click={openCreateDialog}>
        <Plus size={14} /> Ajouter
      </button>
      <button class="btn-ghost btn-export">
        <FileDown size={14} /> Export Report
      </button>
    </div>
    <div class="action-right">
      <select class="filter-select" bind:value={filterStatus}>
        <option value="all">Tout</option>
        <option value="open">\u00c0 faire</option>
        <option value="done">Fait</option>
      </select>
      <select class="filter-select" bind:value={filterSite}>
        {#each SITES as s}
          <option value={s.value}>{s.label}</option>
        {/each}
      </select>
      <div class="search-box">
        <span class="search-icon-wrapper"><Search size={14} /></span>
        <input type="text" placeholder="Rechercher..." on:input={onSearchInput} class="search-input" />
      </div>
    </div>
  </div>

  <!-- Quick filter chips -->
  <div class="chips-bar">
    {#each QUICK_FILTERS as qf}
      <button
        class="chip"
        class:chip-active={quickFilter === qf.key}
        on:click={() => quickFilter = qf.key}
      >
        {qf.label}
      </button>
    {/each}
  </div>

  <!-- ── Content ────────────────────────────────────────── -->
  {#if loading}
    <div class="loading-msg">Chargement...</div>
  {:else if viewMode === 'list'}
    <!-- List view -->
    {#if filteredTasks.length === 0}
      <div class="empty-msg">Aucune t\u00e2che trouv\u00e9e</div>
    {:else}
      {#each sections as [key, section]}
        <div class="section">
          <div class="section-header" style="--section-color: {section.color}">
            <span class="section-title">{section.label}</span>
            <span class="section-count">{section.tasks.length}</span>
          </div>

          <table class="ya-table">
            <thead>
              <tr>
                <th style="width:40px"></th>
                <th style="width:70px">Priorit\u00e9</th>
                <th>T\u00e2che</th>
                <th style="width:120px">Cat\u00e9gorie</th>
                <th style="width:120px">Statut</th>
                <th style="width:80px"></th>
              </tr>
            </thead>
            <tbody>
              {#each section.tasks as task (task.id)}
                <tr class="task-row" class:task-done={task.done}>
                  <td>
                    <button class="task-check" on:click|stopPropagation={() => toggleDone(task)}>
                      {#if task.done}
                        <CheckSquare size={18} class="check-done-icon" />
                      {:else}
                        <Square size={18} class="check-open-icon" />
                      {/if}
                    </button>
                  </td>
                  <td>
                    <span class="priority-pill {getPriorityClass(task.priority)}">
                      {#if task.priority === 3}
                        <AlertTriangle size={11} />
                      {:else if task.priority === 1}
                        <ArrowDown size={11} />
                      {:else}
                        <Equal size={11} />
                      {/if}
                      P{task.priority}
                    </span>
                  </td>
                  <!-- svelte-ignore a11y_click_events_have_key_events -->
                  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
                  <td on:click={() => toggleExpand(task.id)} style="cursor:pointer">
                    <span class="task-title" class:struck={task.done}>{task.title}</span>
                    {#if task.recurrence}
                      <RefreshCw size={12} class="recurrence-icon" />
                    {/if}
                    {#if checklistsCache[task.id] && checklistsCache[task.id].length > 0}
                      {@const prog = getChecklistProgress(task.id)}
                      {#if prog}
                        <span class="checklist-progress">
                          <ListChecks size={11} /> {prog.done}/{prog.total}
                        </span>
                      {/if}
                    {/if}
                  </td>
                  <td>
                    {#if task.category}
                      <span class="task-category">{task.category}</span>
                    {/if}
                  </td>
                  <td>
                    {#if task.due_date || task.done}
                      <span class="status-pill {getStatusBadgeClass(getDueStatus(task))}">
                        <Calendar size={11} />
                        {getDueLabel(getDueStatus(task))}
                      </span>
                    {/if}
                  </td>
                  <td>
                    <div class="task-actions">
                      <button class="btn-icon" on:click|stopPropagation={() => openEditDialog(task)} title="Modifier">
                        <Pencil size={14} />
                      </button>
                      <button class="btn-icon btn-icon-danger" on:click|stopPropagation={() => deleteTask(task)} title="Supprimer">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>

                <!-- Expanded area -->
                {#if expandedTaskId === task.id}
                  <tr class="task-expanded-row">
                    <td colspan="6">
                      <div class="task-expanded">
                        <!-- Notes -->
                        <div class="expanded-section">
                          <div class="expanded-label"><StickyNote size={12} /> Notes</div>
                          {#if editingNotesId === task.id}
                            <textarea class="notes-textarea" bind:value={editingNotesText} rows="3"></textarea>
                            <div class="notes-actions">
                              <button class="btn-small btn-save" on:click={() => saveNotes(task)}>Sauvegarder</button>
                              <button class="btn-small btn-cancel" on:click={cancelEditNotes}>Annuler</button>
                            </div>
                          {:else}
                            <!-- svelte-ignore a11y_click_events_have_key_events -->
                            <!-- svelte-ignore a11y_no_static_element_interactions -->
                            <div class="notes-display" on:click={() => startEditNotes(task)}>
                              {task.notes || 'Cliquer pour ajouter des notes...'}
                            </div>
                          {/if}
                        </div>

                        <!-- Checklist -->
                        <div class="expanded-section">
                          <div class="expanded-label"><ListChecks size={12} /> Checklist</div>
                          {#if checklistsCache[task.id]}
                            {#each checklistsCache[task.id] as item (item.id)}
                              <div class="checklist-item">
                                <button class="cl-check" on:click={() => toggleChecklistItem(task.id, item)}>
                                  {#if item.done}
                                    <CheckSquare size={16} />
                                  {:else}
                                    <Square size={16} />
                                  {/if}
                                </button>
                                <span class="cl-text" class:struck={item.done}>{item.text}</span>
                                <button class="btn-icon-sm" on:click={() => deleteChecklistItem(task.id, item.id)}>
                                  <X size={12} />
                                </button>
                              </div>
                            {/each}
                          {/if}
                          <div class="cl-add-row">
                            <input
                              type="text"
                              class="cl-add-input"
                              placeholder="Nouvel \u00e9l\u00e9ment..."
                              bind:value={newChecklistText[task.id]}
                              on:keydown={(e) => e.key === 'Enter' && addChecklistItem(task.id)}
                            />
                            <button class="btn-small btn-save" on:click={() => addChecklistItem(task.id)}>
                              <Plus size={12} />
                            </button>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                {/if}
              {/each}
            </tbody>
          </table>
        </div>
      {/each}
    {/if}
  {:else if viewMode === 'kanban'}
    <!-- Kanban view -->
    <div class="kanban-board">
      {#each kanbanColumns as col}
        <div class="kanban-column">
          <div class="kanban-header" style="border-bottom-color: {col.color}">
            <span>{col.label}</span>
            <span class="kanban-count">{col.tasks.length}</span>
          </div>
          <div class="kanban-cards">
            {#each col.tasks as task (task.id)}
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <div
                class="kanban-card"
                on:dblclick={() => openEditDialog(task)}
              >
                <div class="kc-title">{task.title}</div>
                {#if task.category}
                  <span class="kc-cat">{task.category}</span>
                {/if}
                {#if task.due_date}
                  <span class="kc-due" style="color: {getDueColor(getDueStatus(task))}">
                    <Calendar size={11} /> {task.due_date}
                  </span>
                {/if}
                {#if task.site}
                  <span class="kc-site"><Building2 size={11} /> {task.site}</span>
                {/if}
              </div>
            {/each}
            {#if col.tasks.length === 0}
              <div class="kanban-empty">Aucune t\u00e2che</div>
            {/if}
          </div>
        </div>
      {/each}
    </div>

  {:else if viewMode === 'stats'}
    <!-- ── Stats View ──────────────────────────────────────── -->
    <div class="stats-view">
      <!-- KPI Row -->
      <div class="stats-kpi-row">
        <div class="stats-kpi">
          <span class="stats-kpi-value">{taskStats.total}</span>
          <span class="stats-kpi-label">Total</span>
        </div>
        <div class="stats-kpi">
          <span class="stats-kpi-value" style="color:var(--success)">{taskStats.done}</span>
          <span class="stats-kpi-label">Termin\u00e9es</span>
        </div>
        <div class="stats-kpi">
          <span class="stats-kpi-value" style="color:var(--info)">{taskStats.open}</span>
          <span class="stats-kpi-label">En cours</span>
        </div>
        <div class="stats-kpi">
          <span class="stats-kpi-value" style="color:var(--danger)">{taskStats.overdue}</span>
          <span class="stats-kpi-label">En retard</span>
        </div>
        <div class="stats-kpi">
          <span class="stats-kpi-value" style="color:var(--primary)">{taskStats.completionRate}%</span>
          <span class="stats-kpi-label">Compl\u00e9tion</span>
        </div>
      </div>

      <div class="stats-grid">
        <!-- By Category -->
        <div class="stats-card">
          <h3><BarChart3 size={14} /> Par cat\u00e9gorie</h3>
          <div class="stats-bars">
            {#each Object.entries(taskStats.byCat).sort((a, b) => b[1].total - a[1].total) as [cat, data]}
              <div class="stats-bar-row">
                <span class="stats-bar-label">{cat}</span>
                <div class="stats-bar-track">
                  <div class="stats-bar-fill done-fill" style="width:{data.total > 0 ? (data.done / data.total * 100) : 0}%"></div>
                </div>
                <span class="stats-bar-numbers">{data.done}/{data.total}</span>
              </div>
            {/each}
            {#if Object.keys(taskStats.byCat).length === 0}
              <p class="stats-empty">Aucune t\u00e2che</p>
            {/if}
          </div>
        </div>

        <!-- By Priority -->
        <div class="stats-card">
          <h3><AlertTriangle size={14} /> T\u00e2ches ouvertes par priorit\u00e9</h3>
          <div class="stats-priority-grid">
            {#each PRIORITIES as prio, i}
              <div class="stats-prio-item">
                <div class="stats-prio-circle" style="border-color:{prio.color};color:{prio.color}">
                  {taskStats.byPrio[i]}
                </div>
                <span class="stats-prio-label">
                  {#if prio.value === 3}<AlertTriangle size={11} />{:else if prio.value === 1}<ArrowDown size={11} />{:else}<Equal size={11} />{/if}
                  {prio.label}
                </span>
              </div>
            {/each}
          </div>
        </div>

        <!-- By Site -->
        <div class="stats-card">
          <h3><Building2 size={14} /> Par site</h3>
          <div class="stats-bars">
            {#each Object.entries(taskStats.bySite).sort((a, b) => b[1].total - a[1].total) as [site, data]}
              <div class="stats-bar-row">
                <span class="stats-bar-label">{site}</span>
                <div class="stats-bar-track">
                  <div class="stats-bar-fill done-fill" style="width:{data.total > 0 ? (data.done / data.total * 100) : 0}%"></div>
                </div>
                <span class="stats-bar-numbers">{data.done}/{data.total}</span>
              </div>
            {/each}
          </div>
        </div>

        <!-- Week activity -->
        <div class="stats-card">
          <h3><BarChart3 size={14} /> Activit\u00e9 7 derniers jours</h3>
          <div class="stats-week-chart">
            {#each taskStats.weekData as day}
              <div class="stats-week-col">
                <div class="stats-week-bars">
                  <div class="stats-week-bar created" style="height:{Math.max(day.created * 20, 2)}px" title="{day.created} cr\u00e9\u00e9es"></div>
                  <div class="stats-week-bar completed" style="height:{Math.max(day.completed * 20, 2)}px" title="{day.completed} termin\u00e9es"></div>
                </div>
                <span class="stats-week-label">{day.label}</span>
              </div>
            {/each}
          </div>
          <div class="stats-week-legend">
            <span class="stats-legend-item"><span class="stats-legend-dot" style="background:var(--info)"></span> Cr\u00e9\u00e9es</span>
            <span class="stats-legend-item"><span class="stats-legend-dot" style="background:var(--success)"></span> Termin\u00e9es</span>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<!-- ── Task Dialog (Modal) ──────────────────────────────── -->
{#if showTaskDialog}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-overlay" on:click={closeTaskDialog}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-box" on:click|stopPropagation>
      <div class="modal-header">
        <h2>{editingTask ? 'Modifier la t\u00e2che' : 'Nouvelle t\u00e2che'}</h2>
        <button class="modal-close" on:click={closeTaskDialog}><X size={18} /></button>
      </div>
      <div class="modal-body">
        <label class="form-label">
          Titre *
          <input type="text" class="form-input" bind:value={dialogForm.title} placeholder="Titre de la t\u00e2che" />
        </label>

        <div class="form-row">
          <label class="form-label form-half">
            Site
            <select class="form-input" bind:value={dialogForm.site}>
              {#each SITES as s}
                <option value={s.value}>{s.label}</option>
              {/each}
            </select>
          </label>
          <label class="form-label form-half">
            Cat\u00e9gorie
            <input type="text" class="form-input" bind:value={dialogForm.category} placeholder="Cat\u00e9gorie"
              list="cat-list"
            />
            <datalist id="cat-list">
              {#each categories as c}
                <option value={c.name} />
              {/each}
            </datalist>
          </label>
        </div>

        <div class="form-row">
          <label class="form-label form-half">
            Priorit\u00e9
            <div class="priority-selector">
              {#each PRIORITIES as p}
                <button
                  class="prio-btn"
                  class:prio-active={dialogForm.priority === p.value}
                  style="--prio-color: {p.color}"
                  on:click={() => dialogForm.priority = p.value}
                >
                  {#if p.value === 3}<AlertTriangle size={11} />{:else if p.value === 1}<ArrowDown size={11} />{:else}<Equal size={11} />{/if}
                  {p.label}
                </button>
              {/each}
            </div>
          </label>
          <label class="form-label form-half">
            R\u00e9currence
            <select class="form-input" bind:value={dialogForm.recurrence}>
              {#each RECURRENCES as r}
                <option value={r.value}>{r.label}</option>
              {/each}
            </select>
          </label>
        </div>

        <label class="form-label">
          <div class="due-date-header">
            \u00c9ch\u00e9ance
            <label class="nodue-label">
              <input type="checkbox" bind:checked={dialogNoDueDate} />
              Sans \u00e9ch\u00e9ance
            </label>
          </div>
          {#if !dialogNoDueDate}
            <input type="date" class="form-input" bind:value={dialogForm.due_date} />
          {/if}
        </label>

        <label class="form-label">
          Notes
          <textarea class="form-input form-textarea" bind:value={dialogForm.notes} rows="3" placeholder="Notes optionnelles..."></textarea>
        </label>
      </div>
      <div class="modal-footer">
        <button class="btn-ghost" on:click={closeTaskDialog}>Annuler</button>
        <button class="btn-primary" on:click={saveTask} disabled={!dialogForm.title.trim()}>
          {editingTask ? 'Modifier' : 'Cr\u00e9er'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ── Template Modal ───────────────────────────────────── -->
{#if showTemplateModal}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-overlay" on:click={closeTemplateModal}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-box modal-wide" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Gestionnaire de templates</h2>
        <button class="modal-close" on:click={closeTemplateModal}><X size={18} /></button>
      </div>
      <div class="modal-body template-body">
        <!-- Left panel: list -->
        <div class="tpl-list-panel">
          <div class="tpl-list-header">
            <span>Templates</span>
            <button class="btn-small btn-save" on:click={() => { selectedTemplateId = null; templateForm = resetTemplateForm(); }}>
              <Plus size={12} /> Nouveau
            </button>
          </div>
          {#each templates as t (t.id)}
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div
              class="tpl-item"
              class:tpl-active={selectedTemplateId === t.id}
              on:click={() => selectTemplate(t)}
            >
              <span class="tpl-name">{t.name}</span>
              <button class="btn-icon-sm" on:click|stopPropagation={() => deleteTemplate(t.id)}>
                <X size={12} />
              </button>
            </div>
          {/each}
          {#if templates.length === 0}
            <div class="tpl-empty">Aucun template</div>
          {/if}
        </div>

        <!-- Right panel: details -->
        <div class="tpl-detail-panel">
          <label class="form-label">
            Nom du template *
            <input type="text" class="form-input" bind:value={templateForm.name} placeholder="Nom unique" />
          </label>
          <label class="form-label">
            Titre de la t\u00e2che
            <input type="text" class="form-input" bind:value={templateForm.title} />
          </label>
          <div class="form-row">
            <label class="form-label form-half">
              Site
              <select class="form-input" bind:value={templateForm.site}>
                {#each SITES as s}
                  <option value={s.value}>{s.label}</option>
                {/each}
              </select>
            </label>
            <label class="form-label form-half">
              Cat\u00e9gorie
              <input type="text" class="form-input" bind:value={templateForm.category} />
            </label>
          </div>
          <div class="form-row">
            <label class="form-label form-half">
              Priorit\u00e9
              <select class="form-input" bind:value={templateForm.priority}>
                {#each PRIORITIES as p}
                  <option value={p.value}>{p.label}</option>
                {/each}
              </select>
            </label>
            <label class="form-label form-half">
              R\u00e9currence
              <select class="form-input" bind:value={templateForm.recurrence}>
                {#each RECURRENCES as r}
                  <option value={r.value}>{r.label}</option>
                {/each}
              </select>
            </label>
          </div>
          <label class="form-label">
            Notes
            <textarea class="form-input form-textarea" bind:value={templateForm.notes} rows="2"></textarea>
          </label>
          <label class="form-label">
            Checklist (JSON array de strings)
            <textarea class="form-input form-textarea" bind:value={templateForm.checklist_json} rows="2" placeholder='["Item 1", "Item 2"]'></textarea>
          </label>

          <div class="tpl-actions">
            {#if !selectedTemplateId}
              <button class="btn-primary" on:click={saveTemplate} disabled={!templateForm.name.trim()}>Cr\u00e9er le template</button>
            {:else}
              <button class="btn-primary" on:click={() => useTemplate(selectedTemplateId)}>Cr\u00e9er une t\u00e2che</button>
            {/if}
          </div>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  /* ── Page ──────────────────────────────────────────────── */
  .tasks-page {
    animation: fadeIn 0.35s ease-out;
  }

  /* ── KPI Badge Row ──────────────────────────────────────── */
  .kpi-badge-row {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }

  .kpi-badge {
    background: var(--bg-card);
    backdrop-filter: blur(16px);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 16px 12px;
    text-align: center;
    transition: border-color 0.2s, transform 0.2s;
    border-top: 3px solid var(--kpi-color);
  }

  .kpi-badge:hover {
    border-color: var(--border-hover);
    transform: translateY(-2px);
  }

  .kpi-count {
    display: block;
    font-size: 28px;
    font-weight: 800;
    color: var(--kpi-color);
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
  }

  .kpi-label {
    display: block;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--text-muted);
    margin-top: 4px;
  }

  /* ── Progress ──────────────────────────────────────────── */
  .progress-wrapper {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 18px;
  }

  .progress-bar {
    flex: 1;
    height: 6px;
    background: var(--overlay-white-5);
    border-radius: 3px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), var(--success));
    border-radius: 3px;
    transition: width 0.4s ease;
  }

  .progress-label {
    font-size: 12px;
    color: var(--text-muted);
    white-space: nowrap;
  }

  /* ── Action bar ────────────────────────────────────────── */
  .action-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 10px;
    flex-wrap: wrap;
  }

  .action-left, .action-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-ghost {
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    color: var(--text-secondary);
    font-size: 13px;
    padding: 6px 14px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .btn-ghost:hover {
    background: var(--bg-hover);
    border-color: var(--border-hover);
    color: var(--text-primary);
  }

  .btn-export {
    border-color: rgba(var(--primary-rgb), 0.3);
    color: var(--primary);
  }
  .btn-export:hover {
    background: rgba(var(--primary-rgb), 0.1);
    border-color: var(--primary);
  }

  .btn-primary {
    background: var(--primary);
    border: none;
    border-radius: 8px;
    color: #fff;
    font-size: 13px;
    font-weight: 600;
    padding: 7px 16px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
    box-shadow: 0 2px 12px rgba(var(--primary-rgb), 0.3);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .btn-primary:hover {
    filter: brightness(1.15);
    box-shadow: 0 4px 20px rgba(var(--primary-rgb), 0.4);
  }

  .btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .filter-select {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 13px;
    padding: 6px 10px;
    font-family: inherit;
    cursor: pointer;
    outline: none;
  }

  .filter-select:focus {
    border-color: var(--primary);
  }

  .search-box {
    position: relative;
    display: flex;
    align-items: center;
  }

  .search-icon-wrapper {
    position: absolute;
    left: 8px;
    font-size: 13px;
    pointer-events: none;
    color: var(--text-muted);
    display: flex;
    align-items: center;
  }

  .search-input {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 13px;
    padding: 6px 10px 6px 28px;
    width: 180px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.15s;
  }

  .search-input:focus {
    border-color: var(--primary);
  }

  /* ── Chips ──────────────────────────────────────────────── */
  .chips-bar {
    display: flex;
    gap: 6px;
    margin-bottom: 18px;
    flex-wrap: wrap;
  }

  .chip {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 20px;
    color: var(--text-secondary);
    font-size: 12px;
    padding: 4px 14px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
  }

  .chip:hover {
    border-color: var(--border-hover);
    color: var(--text-primary);
  }

  .chip-active {
    background: rgba(var(--primary-rgb), 0.15);
    border-color: var(--primary);
    color: var(--primary);
  }

  /* ── Sections ──────────────────────────────────────────── */
  .section {
    margin-bottom: 16px;
  }

  .section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    margin-bottom: 6px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .section-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--section-color);
  }

  .section-count {
    background: var(--section-color);
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    border-radius: 10px;
    padding: 1px 8px;
    min-width: 20px;
    text-align: center;
  }

  /* ── YA Table ──────────────────────────────────────────── */
  .ya-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin-bottom: 4px;
  }

  .ya-table thead th {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border-subtle);
  }

  .ya-table tbody tr.task-row {
    background: var(--bg-card);
    transition: background 0.15s;
  }

  .ya-table tbody tr.task-row:hover {
    background: var(--bg-hover);
  }

  .ya-table tbody tr.task-row td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border-subtle);
    vertical-align: middle;
  }

  .ya-table tbody tr.task-done {
    opacity: 0.5;
  }

  .ya-table tbody tr.task-expanded-row td {
    padding: 0;
    border-bottom: 1px solid var(--border-subtle);
  }

  /* ── Status & Priority Pills ────────────────────────────── */
  .priority-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 20px;
    white-space: nowrap;
  }

  .badge-danger {
    background: rgba(var(--danger-rgb), 0.15);
    color: var(--danger);
  }

  .badge-warning {
    background: rgba(var(--warning-rgb), 0.15);
    color: var(--warning);
  }

  .badge-primary {
    background: rgba(var(--primary-rgb), 0.15);
    color: var(--primary);
  }

  .badge-success {
    background: rgba(var(--success-rgb), 0.15);
    color: var(--success);
  }

  .badge-info {
    background: rgba(var(--info-rgb), 0.15);
    color: var(--info);
  }

  .badge-muted {
    background: var(--overlay-white-5);
    color: var(--text-muted);
  }

  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    white-space: nowrap;
  }

  /* ── Task elements ──────────────────────────────────────── */
  .task-check {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
    line-height: 1;
    flex-shrink: 0;
    display: flex;
    align-items: center;
  }

  .task-check :global(.check-done-icon) { color: var(--success); }
  .task-check :global(.check-open-icon) { color: var(--text-muted); }

  .task-title {
    font-size: 14px;
    color: var(--text-primary);
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .struck {
    text-decoration: line-through;
    color: var(--text-muted);
  }

  .task-category {
    font-size: 11px;
    background: var(--overlay-white-5);
    color: var(--text-secondary);
    padding: 2px 8px;
    border-radius: 6px;
    white-space: nowrap;
  }

  :global(.recurrence-icon) {
    color: var(--text-muted);
    display: inline;
    vertical-align: middle;
    margin-left: 6px;
  }

  .checklist-progress {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
    display: inline-flex;
    align-items: center;
    gap: 3px;
    margin-left: 6px;
  }

  .task-actions {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
    opacity: 0;
    transition: opacity 0.15s;
  }

  .ya-table tbody tr.task-row:hover .task-actions {
    opacity: 1;
  }

  .btn-icon {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    transition: background 0.15s;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
  }

  .btn-icon:hover {
    background: var(--overlay-white-8);
    color: var(--text-primary);
  }

  .btn-icon-danger:hover {
    background: rgba(var(--danger-rgb), 0.15);
    color: var(--danger);
  }

  /* ── Expanded area ─────────────────────────────────────── */
  .task-expanded {
    border-top: 1px solid var(--border-subtle);
    padding: 14px;
    background: var(--bg-base);
    animation: fadeIn 0.2s ease-out;
  }

  .expanded-section {
    margin-bottom: 14px;
  }

  .expanded-section:last-child {
    margin-bottom: 0;
  }

  .expanded-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--text-muted);
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .notes-display {
    font-size: 13px;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 6px 10px;
    border: 1px dashed var(--border-subtle);
    border-radius: 8px;
    min-height: 36px;
    white-space: pre-wrap;
  }

  .notes-display:hover {
    border-color: var(--border-hover);
  }

  .notes-textarea {
    width: 100%;
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 13px;
    padding: 8px 10px;
    resize: vertical;
    font-family: inherit;
    outline: none;
  }

  .notes-textarea:focus {
    border-color: var(--primary);
  }

  .notes-actions {
    display: flex;
    gap: 6px;
    margin-top: 6px;
  }

  .btn-small {
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-family: inherit;
    border: none;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .btn-save {
    background: var(--primary);
    color: #fff;
  }

  .btn-save:hover {
    filter: brightness(1.15);
  }

  .btn-cancel {
    background: transparent;
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
  }

  .btn-cancel:hover {
    background: var(--bg-hover);
  }

  /* ── Checklist items ───────────────────────────────────── */
  .checklist-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 0;
  }

  .cl-check {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
    color: var(--text-muted);
    display: flex;
    align-items: center;
  }

  .cl-text {
    flex: 1;
    font-size: 13px;
    color: var(--text-primary);
  }

  .btn-icon-sm {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-muted);
    padding: 2px;
    border-radius: 4px;
    opacity: 0;
    transition: opacity 0.15s;
    display: flex;
    align-items: center;
  }

  .checklist-item:hover .btn-icon-sm {
    opacity: 1;
  }

  .btn-icon-sm:hover {
    color: var(--danger);
  }

  .cl-add-row {
    display: flex;
    gap: 6px;
    margin-top: 6px;
  }

  .cl-add-input {
    flex: 1;
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 13px;
    padding: 4px 10px;
    font-family: inherit;
    outline: none;
  }

  .cl-add-input:focus {
    border-color: var(--primary);
  }

  /* ── Loading / Empty ───────────────────────────────────── */
  .loading-msg, .empty-msg {
    text-align: center;
    padding: 40px;
    color: var(--text-muted);
    font-size: 14px;
  }

  /* ── View segmented control ─────────────────────────────── */
  .view-segmented {
    display: flex; background: var(--bg-card); border: 1px solid var(--border-subtle);
    border-radius: 8px; overflow: hidden;
  }
  .vseg {
    background: transparent; border: none; color: var(--text-secondary);
    font-size: 12px; padding: 6px 12px; cursor: pointer; font-family: inherit;
    transition: all 0.15s; white-space: nowrap;
    display: flex; align-items: center; gap: 5px;
  }
  .vseg:hover { background: var(--bg-hover); color: var(--text-primary); }
  .vseg-active {
    background: var(--primary); color: #fff;
    box-shadow: 0 2px 8px rgba(var(--primary-rgb), 0.3);
  }

  /* ── Stats View ────────────────────────────────────────── */
  .stats-view { animation: fadeIn 0.3s ease; }
  .stats-kpi-row {
    display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap;
  }
  .stats-kpi {
    flex: 1; min-width: 100px;
    background: var(--bg-card); border: 1px solid var(--border-subtle);
    border-radius: 12px; padding: 16px 20px; text-align: center;
    backdrop-filter: blur(12px);
  }
  .stats-kpi-value { display: block; font-size: 28px; font-weight: 800; color: var(--text-primary); }
  .stats-kpi-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }

  .stats-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
  }
  @media (max-width: 900px) { .stats-grid { grid-template-columns: 1fr; } }
  .stats-card {
    background: var(--bg-card); border: 1px solid var(--border-subtle);
    border-radius: 12px; padding: 18px 20px; backdrop-filter: blur(12px);
  }
  .stats-card h3 {
    margin: 0 0 14px; font-size: 14px; font-weight: 600; color: var(--text-primary);
    display: flex; align-items: center; gap: 6px;
  }

  .stats-bars { display: flex; flex-direction: column; gap: 8px; }
  .stats-bar-row { display: flex; align-items: center; gap: 8px; }
  .stats-bar-label { width: 110px; font-size: 12px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .stats-bar-track { flex: 1; height: 8px; background: var(--overlay-white-5); border-radius: 4px; overflow: hidden; }
  .stats-bar-fill.done-fill { height: 100%; background: linear-gradient(90deg, var(--success), var(--teal)); border-radius: 4px; transition: width 0.5s ease; }
  .stats-bar-numbers { font-size: 11px; color: var(--text-muted); min-width: 40px; text-align: right; font-variant-numeric: tabular-nums; }

  .stats-priority-grid { display: flex; justify-content: space-around; padding: 10px 0; }
  .stats-prio-item { display: flex; flex-direction: column; align-items: center; gap: 8px; }
  .stats-prio-circle {
    width: 56px; height: 56px; border-radius: 50%;
    border: 3px solid; display: flex; align-items: center; justify-content: center;
    font-size: 22px; font-weight: 800;
  }
  .stats-prio-label {
    font-size: 12px; color: var(--text-secondary);
    display: flex; align-items: center; gap: 4px;
  }

  .stats-week-chart { display: flex; justify-content: space-around; align-items: flex-end; height: 100px; padding: 10px 0; }
  .stats-week-col { display: flex; flex-direction: column; align-items: center; gap: 6px; }
  .stats-week-bars { display: flex; gap: 3px; align-items: flex-end; }
  .stats-week-bar { width: 14px; border-radius: 3px 3px 0 0; min-height: 2px; }
  .stats-week-bar.created { background: var(--info); }
  .stats-week-bar.completed { background: var(--success); }
  .stats-week-label { font-size: 10px; color: var(--text-muted); text-transform: capitalize; }
  .stats-week-legend { display: flex; gap: 16px; justify-content: center; margin-top: 8px; }
  .stats-legend-item { display: flex; align-items: center; gap: 4px; font-size: 11px; color: var(--text-secondary); }
  .stats-legend-dot { width: 8px; height: 8px; border-radius: 50%; }
  .stats-empty { color: var(--text-muted); font-size: 13px; text-align: center; padding: 16px; }

  /* ── Kanban ────────────────────────────────────────────── */
  .kanban-board {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
  }

  .kanban-column {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    min-height: 200px;
    display: flex;
    flex-direction: column;
  }

  .kanban-header {
    padding: 12px 14px;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-primary);
    border-bottom: 2px solid;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .kanban-count {
    font-size: 12px;
    background: var(--overlay-white-8);
    padding: 1px 8px;
    border-radius: 10px;
    color: var(--text-muted);
  }

  .kanban-cards {
    padding: 10px;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .kanban-card {
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 10px 12px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }

  .kanban-card:hover {
    border-color: var(--border-hover);
  }

  .kc-title {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 6px;
  }

  .kc-cat, .kc-due, .kc-site {
    font-size: 11px;
    display: inline-flex;
    align-items: center;
    gap: 3px;
    margin-right: 6px;
    margin-top: 2px;
  }

  .kc-cat {
    background: var(--overlay-white-5);
    color: var(--text-secondary);
    padding: 1px 6px;
    border-radius: 4px;
  }

  .kc-site {
    color: var(--text-muted);
  }

  .kanban-empty {
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
    padding: 20px 0;
  }

  /* ── Modal ─────────────────────────────────────────────── */
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.15s ease-out;
  }

  .modal-box {
    background: var(--bg-card-solid);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    width: 480px;
    max-width: 90vw;
    max-height: 85vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  }

  .modal-wide {
    width: 780px;
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 20px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .modal-header h2 {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .modal-close {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    display: flex;
    align-items: center;
  }

  .modal-close:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .modal-body {
    padding: 18px 20px;
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 14px 20px;
    border-top: 1px solid var(--border-subtle);
  }

  /* ── Form elements ─────────────────────────────────────── */
  .form-label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 12px;
  }

  .form-row {
    display: flex;
    gap: 12px;
  }

  .form-half {
    flex: 1;
  }

  .form-input {
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 13px;
    padding: 8px 10px;
    font-family: inherit;
    outline: none;
    width: 100%;
    transition: border-color 0.15s;
  }

  .form-input:focus {
    border-color: var(--primary);
  }

  .form-textarea {
    resize: vertical;
    min-height: 50px;
  }

  .due-date-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .nodue-label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: var(--text-muted);
    cursor: pointer;
  }

  .nodue-label input {
    cursor: pointer;
  }

  /* ── Priority selector ─────────────────────────────────── */
  .priority-selector {
    display: flex;
    gap: 6px;
  }

  .prio-btn {
    flex: 1;
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    color: var(--text-secondary);
    font-size: 12px;
    padding: 6px 4px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
  }

  .prio-btn:hover {
    border-color: var(--prio-color);
    color: var(--prio-color);
  }

  .prio-active {
    background: color-mix(in srgb, var(--prio-color) 15%, transparent);
    border-color: var(--prio-color);
    color: var(--prio-color);
    font-weight: 600;
  }

  /* ── Template modal body ───────────────────────────────── */
  .template-body {
    display: flex;
    gap: 16px;
    min-height: 350px;
  }

  .tpl-list-panel {
    width: 200px;
    flex-shrink: 0;
    border-right: 1px solid var(--border-subtle);
    padding-right: 16px;
  }

  .tpl-list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .tpl-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.15s;
    margin-bottom: 2px;
  }

  .tpl-item:hover {
    background: var(--bg-hover);
  }

  .tpl-active {
    background: rgba(var(--primary-rgb), 0.12);
  }

  .tpl-name {
    font-size: 13px;
    color: var(--text-primary);
  }

  .tpl-empty {
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    padding: 20px 0;
  }

  .tpl-detail-panel {
    flex: 1;
    min-width: 0;
  }

  .tpl-actions {
    margin-top: 14px;
    display: flex;
    gap: 8px;
  }

  /* ── Responsive ────────────────────────────────────────── */
  @media (max-width: 900px) {
    .kpi-badge-row {
      grid-template-columns: repeat(3, 1fr);
    }
    .kanban-board {
      grid-template-columns: 1fr;
    }
    .template-body {
      flex-direction: column;
    }
    .tpl-list-panel {
      width: 100%;
      border-right: none;
      border-bottom: 1px solid var(--border-subtle);
      padding-right: 0;
      padding-bottom: 12px;
    }
  }

  @media (max-width: 600px) {
    .kpi-badge-row {
      grid-template-columns: repeat(2, 1fr);
    }
  }
</style>
