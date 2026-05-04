<script>
  import { whatsNew, markNewSeen } from '../stores/navigation.js';

  // Key of the module whose "what's new" should currently be shown.
  // When set, the modal is visible. Closing the modal sets it to null AND
  // marks the key as seen so the NEW badge disappears in the sidebar.
  export let activeKey = null;

  $: content = activeKey ? whatsNew[activeKey] : null;

  function close() {
    if (activeKey) markNewSeen(activeKey);
    activeKey = null;
  }
</script>

{#if content}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="wn-overlay" on:click|self={close}>
    <div class="wn-dialog">
      <div class="wn-header">
        <span class="wn-emoji">{'✨'}</span>
        <div>
          <span class="wn-since">Nouveautés depuis v{content.since}</span>
          <h2 class="wn-title">{content.title}</h2>
        </div>
        <button class="wn-close" on:click={close} title="Fermer">{'✕'}</button>
      </div>
      <div class="wn-body">
        <ul class="wn-list">
          {#each content.highlights as h}
            <li>{h}</li>
          {/each}
        </ul>
      </div>
      <div class="wn-footer">
        <button class="wn-btn-primary" on:click={close}>J'ai compris</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .wn-overlay {
    position: fixed; inset: 0;
    background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(6px);
    z-index: 9500;
    display: flex; align-items: center; justify-content: center;
    animation: wn-fade 0.18s ease-out;
  }
  @keyframes wn-fade {
    from { opacity: 0; }
    to   { opacity: 1; }
  }
  .wn-dialog {
    width: min(560px, 92vw);
    max-height: 80vh; display: flex; flex-direction: column;
    background: var(--bg-card, #1a1a2e);
    border: 1px solid var(--border-card, rgba(255,255,255,0.1));
    border-radius: 14px;
    box-shadow: 0 25px 60px rgba(0,0,0,0.4);
    animation: wn-pop 0.22s cubic-bezier(0.2, 0.9, 0.4, 1.2);
  }
  @keyframes wn-pop {
    from { opacity: 0; transform: scale(0.92) translateY(10px); }
    to   { opacity: 1; transform: scale(1) translateY(0); }
  }
  .wn-header {
    display: flex; align-items: flex-start; gap: 14px;
    padding: 22px 24px 14px;
    border-bottom: 1px solid var(--border-subtle, rgba(255,255,255,0.06));
  }
  .wn-emoji { font-size: 28px; line-height: 1; flex-shrink: 0; }
  .wn-since {
    font-size: 11px; font-weight: 700; letter-spacing: 0.06em;
    color: var(--primary, #8869e1); text-transform: uppercase;
  }
  .wn-title {
    margin: 4px 0 0; font-size: 18px; font-weight: 700;
    color: var(--text, #E6EAF2);
  }
  .wn-close {
    margin-left: auto; flex-shrink: 0;
    background: transparent; border: none;
    color: var(--text-muted, #94A3B8);
    width: 32px; height: 32px; border-radius: 6px;
    cursor: pointer; font-size: 14px;
  }
  .wn-close:hover { background: rgba(255,255,255,0.08); color: var(--text, #E6EAF2); }

  .wn-body { padding: 16px 24px; overflow-y: auto; }
  .wn-list {
    list-style: none; margin: 0; padding: 0;
    display: flex; flex-direction: column; gap: 10px;
  }
  .wn-list li {
    position: relative; padding-left: 20px;
    font-size: 14px; line-height: 1.5;
    color: var(--text-secondary, #C0C8D6);
  }
  .wn-list li::before {
    content: '\2713';
    position: absolute; left: 0; top: 1px;
    color: var(--primary, #8869e1); font-weight: 700; font-size: 12px;
  }

  .wn-footer {
    display: flex; justify-content: flex-end;
    padding: 14px 24px 20px;
    border-top: 1px solid var(--border-subtle, rgba(255,255,255,0.06));
  }
  .wn-btn-primary {
    background: var(--primary, #8869e1); color: #fff;
    border: none; padding: 9px 20px; border-radius: 8px;
    font-weight: 600; font-size: 14px; cursor: pointer;
    transition: background 0.15s;
  }
  .wn-btn-primary:hover { background: var(--primary-hover, #7058c8); }
</style>
