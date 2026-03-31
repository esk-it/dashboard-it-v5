<script>
  // Simple solid background — replaces the heavy canvas animation
  // The background color is handled by var(--bg-base) in app.css
</script>

<div class="bg-layer"></div>

<style>
  .bg-layer {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 0;
    pointer-events: none;
    background: var(--bg-base);
    transition: background 0.3s ease;
  }
</style>
