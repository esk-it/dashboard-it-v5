<script>
  import { onMount } from 'svelte';

  export let title = '';
  export let value = 0;
  export let hint = '';
  export let orbColor = [69, 43, 144];  // default: primary purple
  export let onClick = null;
  // Optional: 'primary', 'secondary', 'success', 'danger', 'info', 'teal'
  export let colorTheme = '';

  let displayValue = 0;
  let el;
  let tiltX = 0;
  let tiltY = 0;
  let flashing = false;

  // Predefined color themes (YashAdmin style)
  const THEMES = {
    primary:   { bg: 'linear-gradient(135deg, #452B90 0%, #7B5EC6 100%)', text: '#fff', muted: 'rgba(255,255,255,0.7)' },
    secondary: { bg: 'linear-gradient(135deg, #F8B940 0%, #FFD166 100%)', text: '#fff', muted: 'rgba(255,255,255,0.7)' },
    success:   { bg: 'linear-gradient(135deg, #3A9B94 0%, #20c997 100%)', text: '#fff', muted: 'rgba(255,255,255,0.7)' },
    danger:    { bg: 'linear-gradient(135deg, #FF5E5E 0%, #FF9B9B 100%)', text: '#fff', muted: 'rgba(255,255,255,0.7)' },
    info:      { bg: 'linear-gradient(135deg, #58bad7 0%, #89D4E5 100%)', text: '#fff', muted: 'rgba(255,255,255,0.7)' },
    teal:      { bg: 'linear-gradient(135deg, #20c997 0%, #3EDFB5 100%)', text: '#fff', muted: 'rgba(255,255,255,0.7)' },
  };

  $: themeStyle = THEMES[colorTheme] || null;
  $: hasColorBg = !!themeStyle;

  // Count-up animation
  $: if (value !== undefined) {
    animateValue(value);
  }

  function animateValue(target) {
    const start = displayValue;
    const diff = target - start;
    const duration = 600;
    const startTime = performance.now();
    flashing = true;
    setTimeout(() => flashing = false, 400);

    function step(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      displayValue = Math.round(start + diff * eased);
      if (progress < 1) {
        requestAnimationFrame(step);
      }
    }
    requestAnimationFrame(step);
  }

  function handleMouseMove(e) {
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    tiltX = (y - 0.5) * -6;
    tiltY = (x - 0.5) * 6;
  }

  function handleMouseLeave() {
    tiltX = 0;
    tiltY = 0;
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="kpi-card"
  class:clickable={!!onClick}
  class:flash={flashing}
  class:colored={hasColorBg}
  bind:this={el}
  on:mousemove={handleMouseMove}
  on:mouseleave={handleMouseLeave}
  on:click={onClick}
  style="
    {themeStyle ? `background: ${themeStyle.bg};` : ''}
    transform: perspective(800px) rotateX({tiltX}deg) rotateY({tiltY}deg);
  "
>
  {#if !hasColorBg}
    <!-- Orb gradient for non-themed cards -->
    <div
      class="orb"
      style="background: radial-gradient(circle at 80% 20%, rgba({orbColor[0]},{orbColor[1]},{orbColor[2]}, 0.25) 0%, transparent 60%);"
    ></div>
  {:else}
    <!-- Decorative shapes for colored cards -->
    <div class="deco-circle deco-1"></div>
    <div class="deco-circle deco-2"></div>
  {/if}

  <div class="kpi-content">
    <span class="kpi-title" style={themeStyle ? `color: ${themeStyle.muted}` : ''}>{title}</span>
    <span class="kpi-value" style={themeStyle ? `color: ${themeStyle.text}` : ''}>{displayValue}</span>
    {#if hint}
      <span class="kpi-hint" style={themeStyle ? `color: ${themeStyle.muted}` : ''}>{hint}</span>
    {/if}
  </div>
</div>

<style>
  .kpi-card {
    position: relative;
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    padding: 1.25rem;
    overflow: hidden;
    transition: border-color 0.2s ease, transform 0.15s ease, box-shadow 0.3s ease;
    will-change: transform;
    min-width: 0;
    box-shadow: var(--shadow-card);
  }

  .kpi-card.colored {
    border: none;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
  }

  .kpi-card:hover {
    border-color: var(--border-hover);
  }

  .kpi-card.colored:hover {
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.25);
  }

  .kpi-card.clickable {
    cursor: pointer;
  }

  .kpi-card.flash {
    animation: kpiFlash 0.4s ease;
  }

  /* Decorative circles for colored cards */
  .deco-circle {
    position: absolute;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.1);
    pointer-events: none;
  }

  .deco-1 {
    width: 8rem;
    height: 8rem;
    top: -2rem;
    right: -2rem;
  }

  .deco-2 {
    width: 5rem;
    height: 5rem;
    bottom: -1.5rem;
    right: 3rem;
    background: rgba(255, 255, 255, 0.06);
  }

  .orb {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 0;
  }

  .kpi-content {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .kpi-title {
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .kpi-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--text-heading);
    line-height: 1.1;
    animation: countUp 0.6s ease-out;
  }

  .kpi-hint {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 0.125rem;
  }

  @keyframes kpiFlash {
    0% { box-shadow: 0 0 0 rgba(var(--primary-rgb), 0); }
    50% { box-shadow: 0 0 20px rgba(var(--primary-rgb), 0.3); }
    100% { box-shadow: 0 0 0 rgba(var(--primary-rgb), 0); }
  }
</style>
