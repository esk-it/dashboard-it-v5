<script>
  export let padding = '20px';
  export let hover = true;
</script>

<div class="ya-card" class:hoverable={hover} style="padding: {padding}">
  <slot />
</div>

<style>
  .ya-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 1.25rem;
    box-shadow: var(--shadow-card);
    transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
  }

  .hoverable:hover {
    border-color: var(--border-hover);
    transform: translateY(-2px);
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.08);
  }
</style>
