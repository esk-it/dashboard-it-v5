<script>
  import { onMount } from 'svelte';

  export let title = '';
  export let value = 0;
  export let hint = '';
  export let bgColor = '';
  export let icon = '';
  export let onClick = null;
  export let sparkData = [];

  let displayValue = 0;
  let flashing = false;

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

  // Build a tiny sparkline SVG path from sparkData
  $: sparkPath = buildSparkPath(sparkData);

  function buildSparkPath(data) {
    if (!data || data.length < 2) return '';
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    const w = 80;
    const h = 30;
    const stepX = w / (data.length - 1);
    const points = data.map((v, i) => {
      const x = i * stepX;
      const y = h - ((v - min) / range) * (h - 4) - 2;
      return `${x},${y}`;
    });
    return `M${points.join(' L')}`;
  }

  $: sparkAreaPath = buildSparkArea(sparkData);

  function buildSparkArea(data) {
    if (!data || data.length < 2) return '';
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    const w = 80;
    const h = 30;
    const stepX = w / (data.length - 1);
    const points = data.map((v, i) => {
      const x = i * stepX;
      const y = h - ((v - min) / range) * (h - 4) - 2;
      return `${x},${y}`;
    });
    return `M0,${h} L${points.join(' L')} L${w},${h} Z`;
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="kpi-card {bgColor}"
  class:clickable={!!onClick}
  class:flash={flashing}
  class:has-bg={!!bgColor}
  on:click={onClick}
>
  {#if icon}
    <div class="kpi-icon">
      <svelte:component this={icon} size={28} strokeWidth={1.5} />
    </div>
  {/if}

  <div class="kpi-content">
    <span class="kpi-title">{title}</span>
    <span class="kpi-value">{displayValue}</span>
    {#if hint}
      <span class="kpi-hint">{hint}</span>
    {/if}
  </div>

  {#if sparkData.length >= 2}
    <div class="kpi-spark">
      <svg viewBox="0 0 80 30" preserveAspectRatio="none">
        <path d={sparkAreaPath} fill="rgba(255,255,255,0.15)" />
        <path d={sparkPath} fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="1.5" />
      </svg>
    </div>
  {/if}
</div>

<style>
  .kpi-card {
    position: relative;
    background: var(--bg-card);
    border-radius: 1.25rem;
    padding: 1.5rem;
    overflow: hidden;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    min-width: 0;
    color: var(--text-primary);
  }

  .kpi-card.has-bg {
    color: #fff;
    border: none;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
  }

  .kpi-card:not(.has-bg) {
    border: 1px solid var(--border-subtle);
    box-shadow: var(--shadow-card);
  }

  .kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
  }

  .kpi-card.clickable {
    cursor: pointer;
  }

  .kpi-card.flash {
    animation: kpiFlash 0.4s ease;
  }

  .kpi-icon {
    position: absolute;
    top: 1.25rem;
    right: 1.25rem;
    opacity: 0.6;
  }

  .has-bg .kpi-icon {
    opacity: 0.4;
  }

  .kpi-content {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .kpi-title {
    font-size: 13px;
    font-weight: 500;
    opacity: 0.85;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .has-bg .kpi-title {
    color: rgba(255, 255, 255, 0.85);
  }

  :not(.has-bg) .kpi-title {
    color: var(--text-muted);
  }

  .kpi-value {
    font-size: 28px;
    font-weight: 700;
    line-height: 1.2;
  }

  .has-bg .kpi-value {
    color: #fff;
  }

  :not(.has-bg) .kpi-value {
    color: var(--text-primary);
  }

  .kpi-hint {
    font-size: 12px;
    margin-top: 2px;
  }

  .has-bg .kpi-hint {
    color: rgba(255, 255, 255, 0.7);
  }

  :not(.has-bg) .kpi-hint {
    color: var(--text-secondary);
  }

  .kpi-spark {
    position: absolute;
    bottom: 0;
    right: 0;
    width: 50%;
    height: 40px;
    opacity: 0.7;
    pointer-events: none;
  }

  .kpi-spark svg {
    width: 100%;
    height: 100%;
  }

  @keyframes kpiFlash {
    0% { box-shadow: 0 0 0 rgba(var(--primary-rgb), 0); }
    50% { box-shadow: 0 0 20px rgba(var(--primary-rgb), 0.3); }
    100% { box-shadow: 0 0 0 rgba(var(--primary-rgb), 0); }
  }
</style>
