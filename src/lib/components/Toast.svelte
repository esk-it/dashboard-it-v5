<script>
  import { toasts } from '../stores/toast.js';
  import { currentPage } from '../stores/navigation.js';

  const typeColors = {
    success: '#22C55E',
    error: '#EF4444',
    warning: '#F59E0B',
    info: '#3B82F6',
    mail: '#8B5CF6',
    alert_critical: '#EF4444',
  };

  const typeIcons = {
    success: '✅',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️',
    mail: '✉️',
    alert_critical: '🚨',
  };

  function handleClick(toast) {
    if (toast.type === 'mail') currentPage.set('/email');
    if (toast.type === 'alert_critical') currentPage.set('/monitoring');
  }
</script>

<div class="toast-container">
  {#each $toasts as toast (toast.id)}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="toast-item"
      class:toast-mail={toast.type === 'mail'}
      class:toast-critical={toast.type === 'alert_critical'}
      style="border-left-color: {typeColors[toast.type] || typeColors.info}"
      on:click={() => handleClick(toast)}
    >
      <div class="toast-icon-wrap" style="background: {typeColors[toast.type] || typeColors.info}20">
        <span class="toast-icon" class:toast-icon-bounce={toast.type === 'mail'}>{typeIcons[toast.type] || 'ℹ️'}</span>
      </div>
      <div class="toast-body">
        {#if toast.type === 'mail'}
          <span class="toast-title">Nouveau message</span>
        {:else if toast.type === 'alert_critical'}
          <span class="toast-title" style="color:#EF4444">Alerte critique</span>
        {/if}
        <span class="toast-message">{toast.message}</span>
      </div>
    </div>
  {/each}
</div>

<style>
  .toast-container {
    position: fixed;
    top: 80px;
    right: 20px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 10px;
    pointer-events: none;
  }

  .toast-item {
    pointer-events: auto;
    background: var(--bg-card, #1a1a2e);
    border: 1px solid var(--border-subtle, rgba(255,255,255,0.1));
    border-left: 4px solid;
    border-radius: 12px;
    padding: 14px 18px;
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 300px;
    max-width: 420px;
    animation: toastSlideIn 0.4s cubic-bezier(0.21, 1.02, 0.73, 1);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    cursor: default;
  }

  .toast-mail, .toast-critical { cursor: pointer; }
  .toast-mail:hover, .toast-critical:hover {
    transform: translateX(-4px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
  }

  .toast-icon-wrap {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }

  .toast-icon { font-size: 18px; }

  .toast-icon-bounce {
    animation: mailBounce 0.6s ease-in-out 0.3s;
  }

  .toast-body { display: flex; flex-direction: column; gap: 2px; }

  .toast-title {
    font-size: 0.8125rem;
    font-weight: 700;
    color: var(--text-heading, #fff);
  }

  .toast-message {
    font-size: 0.8125rem;
    color: var(--text-secondary, #a2a5b9);
    line-height: 1.4;
  }

  @keyframes toastSlideIn {
    from { opacity: 0; transform: translateX(100px); }
    to { opacity: 1; transform: translateX(0); }
  }

  @keyframes mailBounce {
    0%, 100% { transform: translateY(0); }
    40% { transform: translateY(-8px); }
    60% { transform: translateY(-3px); }
  }
</style>
