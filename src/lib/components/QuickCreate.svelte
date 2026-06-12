<script>
  /**
   * Création rapide globale (raccourci Ctrl+N).
   *
   * v7.5.0 :
   *   - Ajout du Dossier en création rapide (titre + statut initial)
   *   - Style theme-aware (utilise --bg-card / --bg-input / etc)
   *   - Raccourcis numériques 1-8 pour sélectionner une action
   *   - Recherche rapide en haut pour filtrer la liste
   */
  import { createEventDispatcher, onMount } from 'svelte';
  import { currentPage } from '../stores/navigation.js';
  import { api } from '../api/client.js';
  import { success, error as toastError } from '../stores/toast.js';

  const dispatch = createEventDispatcher();

  const ACTIONS = [
    { key: 'task',      emoji: '✅',     label: 'Nouvelle tâche',         path: '/tasks',     fields: ['title'] },
    { key: 'dossier',   emoji: '\u{1F4C1}',  label: 'Nouveau dossier',        path: '/documents', fields: ['title'] },
    { key: 'event',     emoji: '\u{1F4C5}',  label: 'Nouvel événement',       path: '/planning',  fields: ['title'] },
    { key: 'changelog', emoji: '\u{1F4CB}',  label: 'Entrée changelog',       path: '/changelog', fields: ['title'] },
    { key: 'document',  emoji: '\u{1F4C4}',  label: 'Nouveau document',       path: '/documents' },
    { key: 'supplier',  emoji: '\u{1F4C7}',  label: 'Nouveau prestataire',    path: '/suppliers' },
    { key: 'wiki',      emoji: '\u{1F4D6}',  label: 'Nouvelle procédure',     path: '/wiki' },
    { key: 'link',      emoji: '\u{1F680}',  label: 'Nouveau lien rapide',    path: '/launcher' },
  ];

  let selectedAction = null;
  let quickTitle = '';
  let saving = false;
  let filterQuery = '';

  $: filteredActions = ACTIONS.filter(a => {
    if (!filterQuery) return true;
    return a.label.toLowerCase().includes(filterQuery.toLowerCase());
  });

  function close() { dispatch('close'); }

  function selectAction(action) {
    if (action.fields) {
      selectedAction = action;
      quickTitle = '';
      setTimeout(() => {
        const el = document.querySelector('.quick-title-input');
        if (el) el.focus();
      }, 50);
    } else {
      currentPage.set(action.path);
      close();
    }
  }

  async function quickSave() {
    if (!quickTitle.trim() || !selectedAction) return;
    saving = true;
    try {
      if (selectedAction.key === 'task') {
        await api.post('/api/tasks', {
          title: quickTitle, category: '', priority: 2, due_date: null,
          notes: '', site: '', recurrence: '', checklist: [],
        });
        success('Tâche créée');
      } else if (selectedAction.key === 'dossier') {
        await api.post('/api/dossiers', {
          title: quickTitle,
          description: '',
          status: 'demande_envoyee',
          site: '',
          estimated_budget: 0,
        });
        success('Dossier créé');
      } else if (selectedAction.key === 'event') {
        const today = new Date().toISOString().slice(0, 10);
        await api.post('/api/planning/events', {
          title: quickTitle, event_type: 'other', date_start: today,
          date_end: today, all_day: true, time_start: null, time_end: null,
          person: '', notes: '', task_id: null,
        });
        success('Événement créé');
      } else if (selectedAction.key === 'changelog') {
        await api.post('/api/changelog', {
          title: quickTitle, description: '', category: '', impact: 'low',
          author: '', event_date: new Date().toISOString().slice(0, 10), tags: '',
        });
        success('Entrée changelog créée');
      }
      close();
    } catch (e) {
      toastError('Erreur: ' + e.message);
    }
    saving = false;
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      if (selectedAction) {
        selectedAction = null;
        return;
      }
      close();
      return;
    }
    if (e.key === 'Enter' && selectedAction && quickTitle.trim()) {
      quickSave();
      return;
    }
    // Number shortcuts 1-8 to quickly pick an action (only when no action selected
    // and we're not typing into the search/title input)
    if (!selectedAction && /^[1-8]$/.test(e.key)) {
      const tag = document.activeElement?.tagName?.toLowerCase();
      if (tag !== 'input' && tag !== 'textarea') {
        const idx = parseInt(e.key, 10) - 1;
        if (filteredActions[idx]) {
          e.preventDefault();
          selectAction(filteredActions[idx]);
        }
      }
    }
  }

  onMount(() => {
    // Focus the filter input on open for instant typing.
    setTimeout(() => {
      const el = document.querySelector('.qc-filter-input');
      if (el) el.focus();
    }, 50);
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="qc-overlay" on:click|self={close} on:keydown={handleKeydown}>
  <div class="qc-panel">
    <div class="qc-header">
      <span class="qc-icon">{'⚡'}</span>
      <span class="qc-title">Création rapide</span>
      <kbd class="qc-kbd">Ctrl+N</kbd>
    </div>

    {#if !selectedAction}
      <div class="qc-filter">
        <input
          type="text"
          class="qc-filter-input"
          bind:value={filterQuery}
          placeholder="Filtrer…"
          on:keydown={(e) => {
            if (e.key === 'Enter' && filteredActions.length === 1) {
              e.preventDefault();
              selectAction(filteredActions[0]);
            }
          }}
        />
      </div>

      <div class="qc-actions">
        {#each filteredActions as action, i}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div class="qc-action" on:click={() => selectAction(action)}>
            {#if i < 8 && !filterQuery}
              <kbd class="qc-action-num">{i + 1}</kbd>
            {/if}
            <span class="qc-action-emoji">{action.emoji}</span>
            <span class="qc-action-label">{action.label}</span>
            <span class="qc-action-hint">
              {action.fields ? 'Rapide' : 'Ouvrir'}
            </span>
          </div>
        {/each}
        {#if filteredActions.length === 0}
          <div class="qc-empty">Aucune action trouvée.</div>
        {/if}
      </div>
    {:else}
      <div class="qc-quick-form">
        <div class="qc-form-header">
          <button class="qc-back" on:click={() => selectedAction = null}>
            {'←'} Retour
          </button>
          <span>{selectedAction.emoji} {selectedAction.label}</span>
        </div>
        <input
          type="text"
          class="qc-title-input quick-title-input"
          bind:value={quickTitle}
          placeholder="Titre…"
          on:keydown={handleKeydown}
        />
        <button class="qc-submit" on:click={quickSave} disabled={saving || !quickTitle.trim()}>
          {saving ? 'Création…' : 'Créer'}
        </button>
      </div>
    {/if}
  </div>
</div>

<style>
  /* v7.5.0 — full theme-aware restyle. The previous hard-coded dark palette
     was unreadable in light theme. */
  .qc-overlay {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.45);
    z-index: 9500;
    display: flex; align-items: flex-start; justify-content: center;
    padding-top: 18vh;
    backdrop-filter: blur(4px);
    animation: fadeIn 0.12s ease;
  }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

  .qc-panel {
    width: 460px; max-width: 95vw;
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 14px;
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
    overflow: hidden;
    animation: slideDown 0.2s ease;
  }
  @keyframes slideDown {
    from { transform: translateY(-12px); opacity: 0; }
    to   { transform: translateY(0); opacity: 1; }
  }

  .qc-header {
    display: flex; align-items: center; gap: 8px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-card);
  }
  .qc-icon { font-size: 18px; }
  .qc-title { flex: 1; font-size: 14px; font-weight: 700; color: var(--text-heading); }
  .qc-kbd {
    font-size: 10px; padding: 2px 7px; border-radius: 4px;
    background: var(--bg-input); border: 1px solid var(--border-card);
    color: var(--text-muted); font-family: inherit;
  }

  .qc-filter { padding: 10px 14px 6px; }
  .qc-filter-input {
    width: 100%;
    background: var(--bg-input);
    border: 1px solid var(--border-card);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 13px; padding: 9px 12px;
    font-family: inherit; outline: none;
    transition: border-color 0.15s;
  }
  .qc-filter-input:focus { border-color: var(--accent); }
  .qc-filter-input::placeholder { color: var(--text-muted); }

  .qc-actions { padding: 6px; max-height: 50vh; overflow-y: auto; }
  .qc-action {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 14px; border-radius: 10px; cursor: pointer;
    color: var(--text-primary);
    transition: background 0.1s;
  }
  .qc-action:hover { background: var(--bg-input); }
  .qc-action-num {
    font-size: 10px; padding: 2px 6px; border-radius: 4px;
    background: var(--bg-input); border: 1px solid var(--border-card);
    color: var(--text-muted); font-family: inherit;
    min-width: 18px; text-align: center;
  }
  .qc-action:hover .qc-action-num {
    background: var(--accent); color: #fff; border-color: var(--accent);
  }
  .qc-action-emoji { font-size: 18px; width: 26px; text-align: center; }
  .qc-action-label { flex: 1; font-size: 14px; color: var(--text-heading); font-weight: 500; }
  .qc-action-hint {
    font-size: 10px; color: var(--text-muted);
    padding: 2px 8px; border-radius: 4px;
    background: var(--bg-input);
  }
  .qc-empty {
    padding: 24px 14px; text-align: center;
    color: var(--text-muted); font-size: 13px;
  }

  .qc-quick-form { padding: 16px 18px; }
  .qc-form-header {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 14px; font-size: 14px;
    color: var(--text-secondary);
  }
  .qc-back {
    background: none; border: none; color: var(--accent);
    cursor: pointer; font-size: 13px; padding: 4px 10px; border-radius: 6px;
    font-family: inherit; font-weight: 600;
  }
  .qc-back:hover { background: var(--bg-input); }

  .qc-title-input {
    width: 100%;
    background: var(--bg-input);
    border: 1px solid var(--border-card);
    border-radius: 10px;
    color: var(--text-primary);
    font-size: 15px; padding: 12px 14px;
    font-family: inherit; outline: none;
    margin-bottom: 12px;
    transition: border-color 0.15s;
  }
  .qc-title-input:focus { border-color: var(--accent); }
  .qc-title-input::placeholder { color: var(--text-muted); }

  .qc-submit {
    width: 100%;
    background: var(--accent); color: #fff;
    border: none; border-radius: 10px; padding: 11px;
    font-size: 14px; font-weight: 700; cursor: pointer;
    font-family: inherit; transition: filter 0.15s;
    box-shadow: 0 4px 12px rgba(var(--accent-rgb, 136, 105, 225), 0.3);
  }
  .qc-submit:hover:not(:disabled) { filter: brightness(1.08); }
  .qc-submit:disabled { opacity: 0.45; cursor: not-allowed; }
</style>
