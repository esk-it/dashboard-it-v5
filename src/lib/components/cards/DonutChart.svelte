<script>
  import { onMount } from 'svelte';
  import { api } from '../../api/client.js';
  import { Doughnut } from 'svelte-chartjs';
  import {
    Chart as ChartJS,
    ArcElement,
    Tooltip,
    Legend,
  } from 'chart.js';

  ChartJS.register(ArcElement, Tooltip, Legend);

  let categories = [];
  let loading = true;

  // YashAdmin-inspired colors
  const colors = ['#452B90', '#F8B940', '#3A9B94', '#FF5E5E', '#58bad7', '#EC4899', '#FF9F00'];

  export function refresh() {
    fetchData();
  }

  onMount(() => {
    fetchData();
  });

  async function fetchData() {
    loading = true;
    try {
      const data = await api.get('/api/dashboard/stats/categories');
      categories = data.categories || data || [];
    } catch (e) {
      categories = [];
    }
    loading = false;
  }

  $: total = categories.reduce((sum, c) => sum + (c.count || c.value || 0), 0);

  $: chartData = {
    labels: categories.map(c => c.name || c.label || ''),
    datasets: [
      {
        data: categories.map(c => c.count || c.value || 0),
        backgroundColor: colors.slice(0, categories.length),
        borderColor: '#182237',
        borderWidth: 3,
        hoverBorderColor: 'rgba(255, 255, 255, 0.3)',
        hoverOffset: 6,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '70%',
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#182237',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        titleColor: '#fff',
        bodyColor: '#828690',
        padding: 12,
        cornerRadius: 8,
      },
    },
  };
</script>

<div class="donut-widget">
  <div class="donut-chart-area">
    {#if !loading && categories.length > 0}
      <div class="donut-container">
        <Doughnut data={chartData} options={chartOptions} />
        <div class="donut-center">
          <span class="donut-center__value">{total}</span>
          <span class="donut-center__label">Total</span>
        </div>
      </div>
    {:else if loading}
      <div class="donut-empty">Chargement...</div>
    {:else}
      <div class="donut-empty">Aucune donnee</div>
    {/if}
  </div>

  {#if !loading && categories.length > 0}
    <div class="donut-legend">
      {#each categories as cat, i}
        <div class="donut-legend__item">
          <span class="donut-legend__dot" style="background:{colors[i % colors.length]}"></span>
          <span class="donut-legend__name">{cat.name || cat.label}</span>
          <span class="donut-legend__count">{cat.count || cat.value || 0}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .donut-widget {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .donut-chart-area {
    padding: 0.5rem 1rem;
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .donut-container {
    position: relative;
    width: 180px;
    height: 180px;
  }

  .donut-center {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
    display: flex;
    flex-direction: column;
    pointer-events: none;
  }

  .donut-center__value {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text-heading);
    line-height: 1;
  }

  .donut-center__label {
    font-size: 0.6875rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.125rem;
  }

  .donut-empty {
    padding: 2.5rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8125rem;
  }

  /* ── Legend ── */
  .donut-legend {
    padding: 0.75rem 1.25rem;
    border-top: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .donut-legend__item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.75rem;
  }

  .donut-legend__dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .donut-legend__name {
    flex: 1;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .donut-legend__count {
    font-weight: 600;
    color: var(--text-heading);
  }
</style>
