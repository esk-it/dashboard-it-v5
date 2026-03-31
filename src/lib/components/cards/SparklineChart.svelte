<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../../api/client.js';
  import GlassCard from '../GlassCard.svelte';
  import ApexCharts from 'apexcharts';

  let weeklyData = [];
  let loading = true;
  let chartEl;
  let chart;

  export function refresh() {
    fetchData();
  }

  onMount(() => {
    fetchData();
  });

  onDestroy(() => {
    if (chart) chart.destroy();
  });

  async function fetchData() {
    loading = true;
    try {
      const data = await api.get('/api/dashboard/stats/weekly');
      weeklyData = data.values || data.weekly || data || [];
    } catch (e) {
      weeklyData = [0, 0, 0, 0, 0, 0, 0, 0];
    }
    loading = false;
    renderChart();
  }

  function renderChart() {
    if (!chartEl) return;
    if (chart) {
      chart.updateSeries([{ data: weeklyData }]);
      return;
    }

    const options = {
      series: [{
        name: 'Tickets',
        data: weeklyData
      }],
      chart: {
        type: 'area',
        height: 80,
        sparkline: { enabled: true },
        animations: {
          enabled: true,
          easing: 'easeinout',
          speed: 600
        }
      },
      stroke: {
        curve: 'smooth',
        width: 2
      },
      colors: ['#452B90'],
      fill: {
        type: 'gradient',
        gradient: {
          shadeIntensity: 1,
          opacityFrom: 0.4,
          opacityTo: 0.05,
          stops: [0, 100]
        }
      },
      tooltip: {
        enabled: true,
        theme: 'dark',
        x: { show: false },
        y: {
          formatter: (val) => val + ' tickets'
        }
      }
    };

    chart = new ApexCharts(chartEl, options);
    chart.render();
  }

  // Re-render when chartEl becomes available after loading
  $: if (!loading && chartEl && !chart) {
    renderChart();
  }
</script>

<GlassCard padding="0">
  <div class="card-inner">
    <div class="card-header">
      <h3>Tendance hebdomadaire</h3>
    </div>

    <div class="chart-container">
      {#if !loading}
        <div bind:this={chartEl}></div>
      {:else}
        <div class="loading">Chargement...</div>
      {/if}
    </div>
  </div>
</GlassCard>

<style>
  .card-inner {
    display: flex;
    flex-direction: column;
  }

  .card-header {
    padding: 16px 20px 0;
  }

  .card-header h3 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .chart-container {
    padding: 12px 16px 16px;
    min-height: 100px;
  }

  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 80px;
    color: var(--text-muted);
    font-size: 13px;
  }
</style>
