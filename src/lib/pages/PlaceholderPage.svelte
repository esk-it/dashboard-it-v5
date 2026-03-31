<script>
  import { Construction } from 'lucide-svelte';
  export let title = '';
  export let icon = Construction;
</script>

<div class="placeholder">
  <span class="placeholder-icon"><svelte:component this={icon} size={48} /></span>
  <h2>{title}</h2>
  <p>Ce module sera bient&ocirc;t disponible.</p>
</div>

<style>
  .placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 60vh;
    animation: pageSlideIn 0.3s ease-out;
    gap: 12px;
  }

  .placeholder-icon {
    margin-bottom: 8px;
    opacity: 0.6;
    color: var(--text-muted);
  }

  h2 {
    font-size: 24px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  p {
    font-size: 15px;
    color: var(--text-muted);
    margin: 0;
  }
</style>
