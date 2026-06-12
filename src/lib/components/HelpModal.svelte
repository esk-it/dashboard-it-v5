<script>
  /**
   * v7.4.0 — Aide contextuelle par module.
   *
   * Affiche le contenu de `moduleHelp[moduleKey]` dans une fenêtre modale.
   * Si le module n'a pas d'entrée d'aide, on affiche un message de fallback
   * gentil ("module à venir") plutôt qu'une erreur — utile pour les modules
   * récents pas encore documentés.
   */
  import { moduleHelp } from '../stores/navigation.js';
  import { X, BookOpen, Sparkles } from 'lucide-svelte';

  export let moduleKey = '';
  export let open = false;

  $: help = moduleHelp[moduleKey] || null;

  function close() {
    open = false;
  }

  function handleKeydown(e) {
    if (e.key === 'Escape' && open) close();
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
  <div class="help-overlay" on:click|self={close}>
    <div class="help-dialog" role="dialog" aria-modal="true" aria-labelledby="help-title">
      <header class="help-header">
        <div class="help-title-wrap">
          <span class="help-emoji">{help?.emoji || '\u{2139}️'}</span>
          <div>
            <h2 id="help-title">{help?.title || moduleKey}</h2>
            {#if help?.description}
              <p class="help-desc">{help.description}</p>
            {/if}
          </div>
        </div>
        <button class="help-close" on:click={close} title="Fermer (Échap)">
          <X size={18} />
        </button>
      </header>

      <div class="help-body">
        {#if help}
          {#each help.sections || [] as section}
            <section class="help-section">
              <h3>
                <BookOpen size={14} />
                {section.label}
              </h3>
              <ul>
                {#each section.items as item}
                  <li>{item}</li>
                {/each}
              </ul>
            </section>
          {/each}

          {#if help.tips && help.tips.length > 0}
            <section class="help-section help-section--tips">
              <h3>
                <Sparkles size={14} />
                Astuces
              </h3>
              <ul>
                {#each help.tips as tip}
                  <li>{tip}</li>
                {/each}
              </ul>
            </section>
          {/if}
        {:else}
          <p class="help-fallback">
            Pas encore de documentation pour ce module. Si tu as besoin d'infos,
            consulte le CHANGELOG (icône changelog à gauche).
          </p>
        {/if}
      </div>

      <footer class="help-footer">
        <span class="help-footer-hint">Échap pour fermer</span>
        <button class="help-btn-primary" on:click={close}>OK</button>
      </footer>
    </div>
  </div>
{/if}

<style>
  .help-overlay {
    position: fixed; inset: 0;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(2px);
    display: flex; align-items: center; justify-content: center;
    z-index: 9999; padding: 24px;
  }
  .help-dialog {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 14px;
    width: 100%; max-width: 620px;
    max-height: 88vh;
    display: flex; flex-direction: column;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.22);
    overflow: hidden;
  }

  .help-header {
    display: flex; justify-content: space-between; align-items: flex-start;
    gap: 12px; padding: 18px 22px;
    border-bottom: 1px solid var(--border-card);
    flex-shrink: 0;
  }
  .help-title-wrap { display: flex; gap: 14px; align-items: flex-start; flex: 1; min-width: 0; }
  .help-emoji { font-size: 32px; line-height: 1; flex-shrink: 0; }
  .help-title-wrap h2 {
    margin: 0; font-size: 18px; font-weight: 700;
    color: var(--text-heading);
  }
  .help-desc {
    margin: 4px 0 0; font-size: 13px;
    color: var(--text-secondary); line-height: 1.45;
  }
  .help-close {
    background: transparent; border: none;
    color: var(--text-muted); padding: 6px;
    border-radius: 6px; cursor: pointer;
    flex-shrink: 0;
  }
  .help-close:hover { background: var(--bg-input); color: var(--text-heading); }

  .help-body {
    padding: 18px 22px;
    overflow-y: auto;
    display: flex; flex-direction: column; gap: 16px;
    flex: 1; min-height: 0;
  }

  .help-section { display: flex; flex-direction: column; gap: 8px; }
  .help-section h3 {
    margin: 0; padding: 0;
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.5px; color: var(--text-muted);
    display: flex; align-items: center; gap: 6px;
  }
  .help-section ul {
    margin: 0; padding-left: 20px;
    display: flex; flex-direction: column; gap: 4px;
  }
  .help-section li {
    font-size: 13px; color: var(--text-primary);
    line-height: 1.5;
  }

  .help-section--tips {
    padding: 12px 14px; border-radius: 10px;
    background: rgba(var(--accent-rgb), 0.06);
    border: 1px solid rgba(var(--accent-rgb), 0.20);
  }
  .help-section--tips h3 { color: var(--accent); }

  .help-fallback {
    font-size: 13px; color: var(--text-secondary);
    line-height: 1.5; margin: 0;
    padding: 12px 14px; border-radius: 10px;
    background: var(--bg-input);
  }

  .help-footer {
    display: flex; justify-content: space-between; align-items: center;
    gap: 10px; padding: 14px 22px;
    border-top: 1px solid var(--border-card);
    flex-shrink: 0;
  }
  .help-footer-hint { font-size: 11px; color: var(--text-muted); }
  .help-btn-primary {
    background: var(--accent); color: #fff; border: none;
    padding: 8px 18px; border-radius: 8px;
    font-weight: 600; cursor: pointer; font-size: 13px;
    font-family: inherit;
  }
  .help-btn-primary:hover { filter: brightness(1.1); }
</style>
